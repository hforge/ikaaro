# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from datetime import datetime, timedelta
from operator import itemgetter
from string import Template

# Import from itools
from itools.csv import Table as BaseTable
from itools.catalog import (EqQuery, PhraseQuery, RangeQuery, AndQuery,
                            OrQuery, TextField, IntegerField)
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.handlers import ConfigFile, File as FileHandler
from itools.stl import stl
from itools.uri import encode_query, Reference
from itools.xml import XMLParser
from itools.web import FormError

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.forms import TextWidget, BooleanCheckBox
from ikaaro.messages import *
from ikaaro.registry import register_object_class
from ikaaro.table import Table
from ikaaro.text import Text
from ikaaro import widgets
from issue import History, Issue, issue_fields



# Definition of the fields of the forms to add and edit an issue
search_fields = {'search_name': Unicode(),
                 'mtime': Integer(),
                 'module': String(),
                 'version': String(),
                 'type': String(),
                 'priority': String(),
                 'assigned_to': String(),
                 'state': String()}

table_columns = [('id', u'Id'), ('title', u'Title'), ('version', u'Version'),
                 ('module', u'Module'), ('type', u'Type'),
                 ('priority', u'Priority'), ('state', u'State'),
                 ('assigned_to', u'Assigned To'),
                 ('mtime', u'Modified')]


class Tracker(Folder):

    class_id = 'tracker'
    class_version = '20071215'
    class_title = u'Issue Tracker'
    class_description = u'To manage bugs and tasks'
    class_icon16 = 'images/tracker16.png'
    class_icon48 = 'images/tracker48.png'
    class_views = [
        ['search_form'],
        ['add_form'],
        ['browse_content?mode=list'],
        ['edit_metadata_form']]

    __fixed_handlers__ = ['modules', 'versions', 'types',
        'priorities', 'states']


    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        # Versions
        table = VersionsTable()
        table.add_record({'title': u'1.0', 'released': False})
        table.add_record({'title': u'2.0', 'released': False})
        folder.set_handler('%s/versions' % name, table)
        metadata = Versions.build_metadata()
        folder.set_handler('%s/versions.metadata' % name, metadata)
        # Other Tables
        tables = [
            ('modules', [u'Documentation', u'Unit Tests',
                u'Programming Interface', u'Command Line Interface',
                u'Visual Interface']),
            ('types', [u'Bug', u'New Feature', u'Security Issue',
                u'Stability Issue', u'Data Corruption Issue',
                u'Performance Improvement', u'Technology Upgrade']),
            ('priorities', [u'High', u'Medium', u'Low']),
            ('states', [u'Open', u'Fixed', u'Closed'])]
        for table_name, values in tables:
            table = SelectTableTable()
            for title in values:
                table.add_record({'title': title})
            folder.set_handler('%s/%s' % (name, table_name), table)
            metadata = SelectTable.build_metadata()
            folder.set_handler('%s/%s.metadata' % (name, table_name), metadata)
        # Pre-defined stored searches
        open = ConfigFile(state='0')
        not_assigned = ConfigFile(assigned_to='nobody')
        high_priority = ConfigFile(state='0', priority='0')
        i = 0
        for search, title in [(open, u'Open Issues'),
                              (not_assigned, u'Not Assigned'),
                              (high_priority, u'High Priority')]:
            folder.set_handler('%s/s%s' % (name, i), search)
            metadata = StoredSearch.build_metadata(title={'en': title})
            folder.set_handler('%s/s%s.metadata' % (name, i), metadata)
            i += 1


    def get_document_types(self):
        return []


    #######################################################################
    # API
    #######################################################################
    def get_new_id(self, prefix=''):
        ids = []
        for name in self.get_names():
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix):]
            try:
                id = int(name)
            except ValueError:
                continue
            ids.append(id)

        if ids:
            ids.sort()
            return prefix + str(ids[-1] + 1)

        return prefix + '0'


    def get_members_namespace(self, value, not_assigned=False):
        """Returns a namespace (list of dictionaries) to be used for the
        selection box of users (the 'assigned to' and 'cc' fields).
        """
        users = self.get_object('/users')
        members = []
        if not_assigned is True:
            members.append({'id': 'nobody', 'title': 'NOT ASSIGNED'})
        for username in self.get_site_root().get_members():
            user = users.get_object(username)
            members.append({'id': username, 'title': user.get_title()})
        # Select
        if isinstance(value, str):
            value = [value]
        for member in members:
            member['is_selected'] = (member['id'] in value)

        return members


    #######################################################################
    # User Interface
    #######################################################################
    def get_subviews(self, name):
        if name == 'search_form':
            items = list(self.search_objects(object_class=StoredSearch))
            items.sort(lambda x, y: cmp(x.get_property('title'),
                                        y.get_property('title')))
            return ['view?search_name=%s' % x.name for x in items]
        return Folder.get_subviews(self, name)


    def view__sublabel__(self , **kw):
        search_name = kw.get('search_name')
        if search_name is None:
            return u'View'

        search = self.get_object(search_name)
        return search.get_title()


    #######################################################################
    # User Interface / View
    search_form__access__ = 'is_allowed_to_view'
    search_form__label__ = u'Search'
    search_form__icon__ = 'button_search.png'
    def search_form(self, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Build the namespace
        namespace = {}
        # Stored Searches
        stored_searches = [
            {'name': x.name, 'title': x.get_title()}
            for x in self.search_objects(object_class=StoredSearch) ]
        stored_searches.sort(key=itemgetter('title'))
        namespace['stored_searches'] = stored_searches

        # Search Form
        search_name = context.get_form_value('search_name')
        if search_name:
            search = self.get_object(search_name)
            get_value = search.handler.get_value
            get_values = search.get_values
            namespace['search_name'] = search_name
            namespace['search_title'] = search.get_property('title')
        else:
            get_value = context.get_form_value
            get_values = context.get_form_values
            namespace['search_name'] = get_value('search_name')
            namespace['search_title'] = get_value('search_title')

        namespace['text'] = get_value('text', type=Unicode)
        namespace['mtime'] = get_value('mtime', type=Integer)
        module = get_values('module', type=Integer)
        type = get_values('type', type=Integer)
        version = get_values('version', type=Integer)
        priority = get_values('priority', type=Integer)
        assign = get_values('assigned_to')
        state = get_values('state', type=Integer)

        get = self.get_object
        namespace['modules'] = get('modules').get_options(module)
        namespace['types'] = get('types').get_options(type)
        namespace['versions'] = get('versions').get_options(version)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        namespace['states'] = get('states').get_options(state, sort=False)
        namespace['users'] = self.get_members_namespace(assign, True)

        # is_admin
        ac = self.get_access_control()
        namespace['is_admin'] = ac.is_admin(context.user, self)
        pathto_website = self.get_pathto(self.get_site_root())
        namespace['manage_assigned'] = '%s/;permissions_form' % pathto_website

        handler = self.get_object('/ui/tracker/search.xml')
        return stl(handler, namespace)


    search__access__ = 'is_allowed_to_edit'
    def search(self, context):
        try:
            form = context.check_form_input(search_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=[])
        search_name = context.get_form_value('search_name')
        search_title = context.get_form_value('search_title').strip()
        search_title = unicode(search_title, 'utf8')

        stored_search = stored_search_title = None
        if not search_title:
            context.uri.query['search_name'] = search_name = None
        if search_name:
            # Edit an Stored Search
            try:
                stored_search = self.get_object(search_name)
                stored_search_title = stored_search.get_property('title')
            except LookupError:
                pass

        if search_title and search_title != stored_search_title:
            # New Stored Search
            search_name = self.get_new_id('s')
            stored_search = StoredSearch.make_object(StoredSearch, self,
                                                     search_name)

        if stored_search is None:
            # Just Search
            return context.uri.resolve(';view').replace(**context.uri.query)

        # Edit / Title
        context.commit = True
        stored_search.set_property('title', search_title, 'en')
        # Edit / Search Values
        text = context.get_form_value('text').strip().lower()
        stored_search.handler.set_value('text', text)

        mtime = context.get_form_value('mtime', type=Integer, default=0)
        stored_search.handler.set_value('mtime', str(mtime))

        criterias = [('module', Integer), ('version', Integer),
            ('type', Integer), ('priority', Integer), ('assigned_to', String),
            ('state', Integer)]
        for name, type in criterias:
            value = context.get_form_values(name, type=type)
            stored_search.set_values(name, value, type=type)

        return context.uri.resolve(';view?search_name=%s' % search_name)


    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    view__icon__ = 'view.png'
    def view(self, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        namespace = {}
        namespace['method'] = 'GET'
        namespace['action'] = '.'
        # Get search results
        results = self.get_search_results(context)
        # Analyse the result
        if isinstance(results, Reference):
            return results
        # Selected issues
        selected_issues = context.get_form_values('ids')
        # Show checkbox or not
        show_checkbox = False
        actions = []
        if (context.get_form_value('export_to_text') or
            context.get_form_value('export_to_csv') or
            context.get_form_value('change_several_bugs')):
            show_checkbox = True
        # Construct lines
        lines = []
        for issue in results:
            line = issue.get_informations()
            # Add link to title
            link = '%s/;edit_form' % issue.name
            line['title'] = (line['title'], link)
            if show_checkbox:
                line['checkbox'] = True
                if not selected_issues:
                  line['checked'] = True
                else:
                    if issue.name in selected_issues:
                        line['checked'] = issue.name
            lines.append(line)
        # Sort
        sortby = context.get_form_value('sortby', default='id')
        sortorder = context.get_form_value('sortorder', default='up')
        if sortby == 'mtime':
            lines.sort(key=itemgetter('mtime_sort'))
        else:
            lines.sort(key=itemgetter(sortby))
        if sortorder == 'down':
            lines.reverse()
        # Set title of search
        search_name = context.get_form_value('search_name')
        if search_name:
            search = self.get_object(search_name)
            title = search.get_title()
        else:
            title = self.gettext(u'View Tracker')
        nb_results = len(lines)
        namespace['title'] = title
        # Keep the search_parameters, clean different actions
        params = encode_query(context.uri.query)
        params = params.replace('change_several_bugs=1', '')
        params = params.replace('export_to_csv=1', '')
        params = params.replace('export_to_text=1', '')
        params = params.replace('&&', '&').replace('?&', '?').replace('&#', '#')
        namespace['search_parameters'] = params
        criteria = []
        for key in ['search_name', 'mtime']:
            value = context.get_form_value(key)
            criteria.append({'name': key, 'value': value})
        keys = 'module', 'version', 'type', 'priority', 'assigned_to', 'state'
        for key in keys:
            values = context.get_form_values(key)
            for value in values:
                criteria.append({'name': key, 'value': value})
        namespace['criteria'] = criteria
        # Table
        sortby = context.get_form_value('sortby', default='id')
        sortorder = context.get_form_value('sortorder', default='up')
        msgs = (u'<span>There is 1 result.</span>',
                u'<span>There are ${n} results.</span>')
        namespace['batch'] = widgets.batch(context.uri, 0, nb_results,
                                nb_results, msgs=msgs)
        namespace['table'] = widgets.table(table_columns, lines, [sortby],
                            sortorder, actions=actions, table_with_form=False)
        namespace['nb_results'] = nb_results
        # Export_to_text
        namespace['export_to_text'] = False
        if context.get_form_value('export_to_text'):
            namespace['method'] = 'GET'
            namespace['action'] = ';view'
            namespace['export_to_text'] = True
            namespace['columns'] = []
            # List columns
            columns = context.get_form_values('column_selection')
            # Put the title at the end
            table_columns.remove(('title', u'Title'))
            table_columns.append(('title', u'Title'))
            for column in table_columns:
                name, title = column
                if name is not 'id':
                    checked = True
                    if context.get_form_value('button_export_to_text'):
                        checked = name in columns
                    namespace['columns'].append({'name': name,
                                                 'title': title,
                                                 'checked': checked})
            namespace['text'] = self.get_export_to_text(context)
        # Export_to_csv
        namespace['export_to_csv'] = False
        if context.get_form_value('export_to_csv'):
            namespace['export_to_csv'] = True
            namespace['method'] = 'GET'
            namespace['action'] = ';export_to_csv'
        # Edit several bugs at once
        namespace['change_several_bugs'] = False
        if context.get_form_value('change_several_bugs'):
            get = self.get_object
            namespace['method'] = 'POST'
            namespace['action'] = ';change_several_bugs'
            namespace['change_several_bugs'] = True
            namespace['modules'] = get('modules').get_options()
            namespace['versions'] = get('versions').get_options()
            namespace['priorities'] = get('priorities').get_options()
            namespace['states'] = get('states').get_options()
            namespace['types'] = get('types').get_options()
            namespace['states'] = get('states').get_options()
            users = self.get_object('/users')
            namespace['users'] = self.get_members_namespace('')

        handler = self.get_object('/ui/tracker/view_tracker.xml')
        return stl(handler, namespace)


    export_to_csv__access__ = 'is_allowed_to_view'
    export_to_csv__label__ = u'Export to CSV'
    def export_to_csv(self, context):
        # Get search results
        results = self.get_search_results(context)
        # Analyse the results
        if isinstance(results, Reference):
            return results
        # Get CSV encoding and separator
        editor = context.get_form_value('editor')
        if editor=='oo':
            # OpenOffice
            separator = ','
            encoding = 'utf-8'
        else:
            # Excel
            separator = ';'
            encoding = 'cp1252'
        # Selected issues
        selected_issues = context.get_form_values('ids')
        # Create the CSV
        csv_lines = []
        for issue in results:
            if selected_issues and (issue.name not in selected_issues):
                continue
            csv_line = ''
            issue_line = issue.get_informations()
            for column in table_columns:
                name, value = column
                val = issue_line[name]
                if csv_line:
                    csv_line = '%s%s%s' % (csv_line, separator, val)
                else:
                    csv_line = '%s' % val
            csv_lines.append(csv_line)
        data = '\n'.join(csv_lines)
        if not len(data):
            return context.come_back(u"No data to export.")
        # Set response type
        response = context.response
        response.set_header('Content-Type', 'text/csv')
        response.set_header('Content-Disposition',
                            'attachment; filename=export.csv')
        return data.encode(encoding)


    change_several_bugs__access__ = 'is_allowed_to_view'
    change_several_bugs__label__ = u'Change Several Issues'
    def change_several_bugs(self, context):
        root = context.root
        # Get search results
        results = self.get_search_results(context)
        # Analyse the result
        if isinstance(results, Reference):
            return results
        users_issues = {}
        # Comment
        comment = context.get_form_value('comment', type=Unicode)
        # Selected_issues
        selected_issues = context.get_form_values('ids')
        # Modify all issues selected
        for issue in results:
            if issue.name not in selected_issues:
                  continue
            assigned_to = issue.get_value('assigned_to')
            # Create a new record
            record = {}
            record['datetime'] = datetime.now()
            # User
            user = context.user
            if user is None:
                record['username'] = ''
            else:
                record['username'] = user.name
            # Title (Is the same)
            record['title'] = issue.get_value('title')
            # Other changes
            for name in ['module', 'version', 'type', 'priority',
                         'assigned_to', 'state']:
                type = History.schema[name]
                last_value = issue.get_value(name)
                new_value = context.get_form_value('change_%s' % name, type=type)
                if ((last_value==new_value) or (new_value is None) or
                    (new_value=='do_not_change')):
                    # If no modification set the last value
                    value = last_value
                else:
                    value = new_value
                if type == Unicode:
                    value = value.strip()
                record[name] = value
            # CC
            record['cc_list'] = issue.get_value('cc_list')
            # Comment
            record['comment'] = comment
            # No attachment XXX
            record['file'] = ''
            # Add the list of modifications to comment XXX
            modifications = issue.get_diff_with(record, context)
            if modifications:
                title = self.gettext(u'Modifications:')
                record['comment'] += u'\n\n%s\n\n%s' % (title, modifications)
            # Save issue
            history = issue.handler.get_handler('.history')
            history.add_record(record)
            # Mail (create a dict with a list of issues for each user)
            new_assigned_to = context.get_form_value('assigned_to')
            info = {'href': context.uri.resolve(self.get_pathto(issue)),
                    'name': issue.name,
                    'title': issue.get_title()}
            if assigned_to:
                if not users_issues.has_key(assigned_to):
                    users_issues[assigned_to] = []
                users_issues[assigned_to].append(info)
            if new_assigned_to and (assigned_to != new_assigned_to):
                if not users_issues.has_key(new_assigned_to):
                    users_issues[new_assigned_to] = []
                users_issues[new_assigned_to].append(info)
            # Change
            context.server.change_object(issue)
        # Send mails
        user = context.user
        if user is None:
            user_title = self.gettext(u'ANONYMOUS')
        else:
            user_title = user.get_title()
        template = u'--- Comment from : $user ---\n\n$comment\n\n$issues'
        template = self.gettext(template)
        tracker_title = self.parent.get_property('title') or 'Tracker Issue'
        subject = u'[%s]' % tracker_title
        for user_id in users_issues.keys():
            user_issues = []
            for user_issue in users_issues[user_id]:
                href = user_issue['href']
                name = user_issue['name']
                title = user_issue['title']
                user_issues.append(u'#%s - %s - %s' %(name, title, href))
            body = Template(template).substitute(user=user_title,
                                                 comment=comment,
                                                 issues='\n'.join(user_issues))
            to_addr = root.get_user(user_id).get_property('email')
            root.send_email(to_addr, subject, text=body)

        # Redirect on the new search
        query = encode_query(context.uri.query)
        reference = ';view?%s&change_several_bugs=1#link' % query
        goto = context.uri.resolve(reference)

        keys = context.get_form_keys()
        keep = [key for key in ['search_name', 'mtime', 'module', 'version',
                                'type', 'priority', 'assigned_to', 'state']
                 if key in keys]
        return context.come_back(message=MSG_CHANGES_SAVED, goto=goto,
                                    keep=keep)


    def get_export_to_text(self, context):
        """Generate a text with selected records of selected issues
        """
        # Get selected columns
        selected_columns = context.get_form_values('column_selection')
        if not selected_columns:
            selected_columns = [ x[0] for x in table_columns
                                 if x[0] is not 'id' ]
        # Get search results
        results = self.get_search_results(context)
        # Analyse the result
        if isinstance(results, Reference):
            return results
        # Selected issues
        selected_issues = context.get_form_values('ids')
        # Get lines
        lines = []
        for issue in results:
            # If selected_issues=None, select all
            if selected_issues and (issue.name not in selected_issues):
                continue
            lines.append(issue.get_informations())
        # Sort lines
        sortby = context.get_form_value('sortby', default='id')
        sortorder = context.get_form_value('sortorder', default='up')
        lines.sort(key=itemgetter(sortby))
        if sortorder == 'down':
            lines.reverse()
        # Create the text
        tab_text = []
        for line in lines:
            filtered_line = [unicode(line[col]) for col in selected_columns]
            id = Template(u'#$id').substitute(id=line['name'])
            filtered_line.insert(0, id)
            filtered_line = u'\t'.join(filtered_line)
            tab_text.append(filtered_line)
        return u'\n'.join(tab_text)


    def get_search_results(self, context):
        """Method that return a list of issues that correspond to the search
        """
        try:
            form = context.check_form_input(search_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=[])
        users = self.get_object('/users')
        # Choose stored Search or personalized search
        search_name = form['search_name']
        if search_name:
            search = self.get_object(search_name)
            get_value = search.handler.get_value
            get_values = search.get_values
        else:
            get_value = context.get_form_value
            get_values = context.get_form_values
        # Get search criteria
        text = get_value('text', type=Unicode)
        if text is not None:
            text = text.strip().lower()
        mtime = get_value('mtime', type=Integer)
        modules = get_values('module', type=Integer)
        versions = get_values('version', type=Integer)
        types = get_values('type', type=Integer)
        priorities = get_values('priority', type=Integer)
        assigns = get_values('assigned_to', type=String)
        states = get_values('state', type=Integer)

        # Build the query
        abspath = self.get_canonical_path()
        query = EqQuery('parent_path', str(abspath))
        query = AndQuery(query, EqQuery('format', 'issue'))
        if text:
            query2 = [ OrQuery(EqQuery('title', word), EqQuery('text', word))
                               for word, kk in TextField.split(text) ]
            query = AndQuery(query, *query2)
        for name, data in (('module', modules), ('version', versions),
                           ('type', types), ('priority', priorities),
                           ('state', states)):
            if data != []:
                query2 = []
                for value in data:
                    word = IntegerField.split(value).next()[0]
                    query2.append(EqQuery(name, word))
                query = AndQuery(query, OrQuery(*query2))
        if mtime:
            date = datetime.now() - timedelta(mtime)
            date = date.strftime('%Y%m%d%H%M%S')
            query = AndQuery(query, RangeQuery('mtime', date, None))
        if assigns != []:
            query2 = []
            for value in assigns:
                if value == '':
                    value = 'nobody'
                query2.append(EqQuery('assigned_to', value))
            query = AndQuery(query, OrQuery(*query2))

        # Execute the search
        root = context.root
        results = root.search(query)
        issues = []
        for doc in results.get_documents():
            object = root.get_object(doc.abspath)
            # Append
            issues.append(object)
        return issues


    #######################################################################
    # User Interface / Add Issue
    add_form__access__ = 'is_allowed_to_edit'
    add_form__label__ = u'Add'
    add_form__icon__ = 'new.png'
    def add_form(self, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Build the namespace
        namespace = {}
        namespace['title'] = context.get_form_value('title', type=Unicode)
        namespace['comment'] = context.get_form_value('comment', type=Unicode)
        # Others
        get = self.get_object
        module = context.get_form_value('module', type=Integer)
        namespace['modules'] = get('modules').get_options(module)
        version = context.get_form_value('version', type=Integer)
        namespace['versions'] = get('versions').get_options(version)
        type = context.get_form_value('type', type=Integer)
        namespace['types'] = get('types').get_options(type)
        priority = context.get_form_value('priority', type=Integer)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        state = context.get_form_value('state', type=Integer)
        namespace['states'] = get('states').get_options(state, sort=False)

        users = self.get_object('/users')
        assigned_to = context.get_form_values('assigned_to', type=String)
        namespace['users'] = self.get_members_namespace(assigned_to)

        namespace['cc_add'] = self.get_members_namespace(())

        handler = self.get_object('/ui/tracker/add_issue.xml')
        return stl(handler, namespace)


    add_issue__access__ = 'is_allowed_to_edit'
    def add_issue(self, context):
        keep = ['title', 'version', 'type', 'state', 'module', 'priority',
                'assigned_to', 'cc_add', 'comment']
        # Check input data
        try:
            form = context.check_form_input(issue_fields)
        except:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=keep)

        # Add
        id = self.get_new_id()
        issue = Issue.make_object(Issue, self, id)
        issue._add_record(context)

        goto = context.uri.resolve2('../%s/;edit_form' % issue.name)
        return context.come_back(u'New issue addded.', goto=goto)


    go_to_issue__access__ = 'is_allowed_to_view'
    def go_to_issue(self, context):
        issue_name = context.get_form_value('issue_name')
        if not issue_name:
            return context.come_back(MSG_NAME_MISSING)

        if not self.has_object(issue_name):
            return context.come_back(u'Issue not found.')

        issue = self.get_object(issue_name)
        if not isinstance(issue, Issue):
            return context.come_back(u'Issue not found.')

        return context.uri.resolve2('../%s/;edit_form' % issue_name)



###########################################################################
# Tables
###########################################################################
class SelectTableTable(BaseTable):

    schema = {'title': Unicode}

    form = [TextWidget('title', title=u'Title')]


class SelectTable(Table):

    class_id = 'tracker_select_table'
    class_version = '20071216'
    class_title = u'Select Table'
    class_handler = SelectTableTable


    def get_options(self, value=None, sort=True):
        table = self.handler
        options = [ {'id': x.id, 'title': x.title}
                    for x in table.get_records() ]
        if sort is True:
            options.sort(key=lambda x: x['title'])
        # Set 'is_selected'
        if value is None:
            for option in options:
                option['is_selected'] = False
        elif isinstance(value, list):
            for option in options:
                option['is_selected'] = (option['id'] in value)
        else:
            for option in options:
                option['is_selected'] = (option['id'] == value)

        return options


    def view(self, context):
        namespace = {}

        # The input parameters
        start = context.get_form_value('batchstart', type=Integer, default=0)
        size = 30

        # The batch
        total = self.handler.get_n_records()
        namespace['batch'] = widgets.batch(context.uri, start, size, total,
                                           self.gettext)

        # The table
        actions = []
        if total:
            ac = self.get_access_control()
            if ac.is_allowed_to_edit(context.user, self):
                actions = [('del_record_action', u'Remove',
                            'button_delete', None)]

        fields = [('id', u'id')]
        for widget in self.handler.form:
            fields.append((widget.name, getattr(widget, 'title', widget.name)))

        fields.append(('issues', u'Issues'))
        records = []

        getter = lambda x, y: x.get_value(y)

        filter = self.name[:-1]
        if self.name.startswith('priorit'):
            filter = 'priority'

        root = context.root
        abspath = self.parent.get_canonical_path()
        base_query = EqQuery('parent_path', str(abspath))
        base_query = AndQuery(base_query, EqQuery('format', 'issue'))
        for record in self.handler.get_records():
            id = record.id
            records.append({})
            records[-1]['checkbox'] = True
            # Fields
            records[-1]['id'] = id, ';edit_record_form?id=%s' % id
            for field, field_title in fields[1:-1]:
                value = self.handler.get_value(record, field)
                datatype = self.handler.get_datatype(field)

                multiple = getattr(datatype, 'multiple', False)
                if multiple is True:
                    value.sort()
                    if len(value) > 0:
                        rmultiple = len(value) > 1
                        value = value[0]
                    else:
                        rmultiple = False
                        value = None

                is_enumerate = getattr(datatype, 'is_enumerate', False)
                if is_enumerate:
                    records[-1][field] = datatype.get_value(value)
                else:
                    records[-1][field] = value

                if multiple is True:
                    records[-1][field] = (records[-1][field], rmultiple)

            filter_value = IntegerField.split(id).next()[0]
            query = AndQuery(base_query, EqQuery(filter, filter_value))
            count = root.search(query).get_n_documents()
            value = '0'
            if count != 0:
                value = '<a href="../;view?%s=%s">%s issues</a>'
                if count == 1:
                    value = '<a href="../;view?%s=%s">%s issue</a>'
                value = XMLParser(value % (filter, id, count))
            records[-1]['issues'] = value

        # Sorting
        sortby = context.get_form_value('sortby')
        sortorder = context.get_form_value('sortorder', default='up')
        if sortby:
            records.sort(key=itemgetter(sortby), reverse=(sortorder=='down'))

        records = records[start:start+size]
        for record in records:
            for field, field_title in fields[1:]:
                if isinstance(record[field], tuple):
                    if record[field][1] is True:
                        record[field] = '%s [...]' % record[field][0]
                    else:
                        record[field] = record[field][0]

        namespace['table'] = widgets.table(fields, records, [sortby],
                                           sortorder, actions)

        handler = self.get_object('/ui/table/view.xml')
        return stl(handler, namespace)


    def del_record_action(self, context):
        # check input
        ids = context.get_form_values('ids', type=Integer)
        if not ids:
            return context.come_back(u'No objects selected.')

        filter = self.name[:-1]
        if self.name.startswith('priorit'):
            filter = 'priority'
        root = context.root
        abspath = self.parent.get_canonical_path()

        # Search
        base_query = EqQuery('parent_path', str(abspath))
        base_query = AndQuery(base_query, EqQuery('format', 'issue'))
        removed = []
        for id in ids:
            filter_value = IntegerField.split(id).next()[0]
            query = AndQuery(base_query, EqQuery(filter, filter_value))
            count = root.search(query).get_n_documents()
            if count == 0:
                self.handler.del_record(id)
                removed.append(str(id))

        message = u'Objects removed: $objects.'
        return context.come_back(message, objects=', '.join(removed))


    #######################################################################
    # Update
    #######################################################################
    def update_20071216(self, columns=['id', 'title']):
        """Change from CSV to Table.
        """
        old_name = self.name
        new_name = old_name[:-4]

        folder = self.parent.handler
        csv = FileHandler('%s/%s' % (folder.uri, old_name)).to_str()
        table = self.class_handler()
        table.update_from_csv(csv, columns)
        # Replace
        folder.del_handler(old_name)
        folder.set_handler(new_name, table)
        # Rename
        folder.move_handler('%s.metadata' % old_name, '%s.metadata' % new_name)



class VersionsTable(BaseTable):

    schema = {'title': Unicode(),
              'released': Boolean()}

    form = [TextWidget('title', title=u'Title'),
            BooleanCheckBox('released', title=u'Released')]


class Versions(SelectTable):

    class_id = 'tracker_versions'
    class_version = '20071216'
    class_handler = VersionsTable


    #######################################################################
    # Update
    #######################################################################
    def update_20071216(self):
        SelectTable.update_20071216(self, ['id', 'title', 'released'])



###########################################################################
# Stored Searches
###########################################################################
class StoredSearch(Text):

    class_id = 'stored_search'
    class_version = '20071215'
    class_title = u'Stored Search'
    class_handler = ConfigFile


    def get_values(self, name, type=String):
        value = self.handler.get_value(name, default='')
        return [ type.decode(x) for x in value.split() ]


    def set_values(self, name, value, type=String):
        value = [ type.encode(x) for x in value ]
        value = ' '.join(value)
        self.handler.set_value(name, value)



###########################################################################
# Register
###########################################################################
register_object_class(Tracker)
register_object_class(SelectTable)
register_object_class(Versions)
register_object_class(StoredSearch)
