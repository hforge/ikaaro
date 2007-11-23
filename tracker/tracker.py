# -*- coding: UTF-8 -*-
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
from datetime import datetime
import mimetypes
from operator import itemgetter
from string import Template
from re import sub

# Import from itools
from itools.datatypes import Boolean, DateTime, Integer, String, Unicode, XML
from itools.i18n import format_datetime
from itools.handlers import ConfigFile, Table as BaseTable
from itools.rest import checkid
from itools.xml import XMLParser
from itools.stl import stl
from itools.uri import encode_query, Reference, Path

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.messages import *
from ikaaro.table import Table
from ikaaro.text import Text
from ikaaro.utils import generate_name
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.versioning import VersioningAware
from ikaaro import widgets



# Definition of the fields of the forms to add and edit an issue
issue_fields = [('title', True), ('version', True), ('type', True),
    ('state', True), ('module', False), ('priority', False),
    ('assigned_to', False), ('comment', False), ('file', False)]


search_fields = [('search_name', False, Unicode),
                 ('mtime', False, Integer),
                 ('module', False),
                 ('version', False),
                 ('type', False),
                 ('priority', False),
                 ('assigned_to', False),
                 ('state', False)]

table_columns = [('id', u'Id'), ('title', u'Title'), ('version', u'Version'),
                 ('module', u'Module'), ('type', u'Type'),
                 ('priority', u'Priority'), ('state', u'State'),
                 ('assigned_to', u'Assigned To'),
                 ('mtime', u'Modified')]


class Tracker(Folder):

    class_id = 'tracker'
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
        open = ConfigFile(state=0)
        not_assigned = ConfigFile(assigned_to='nobody')
        high_priority = ConfigFile(state=0, priority=0)
        i = 0
        for search, title in [(open, u'Open Issues'),
                              (not_assigned, u'Not Assigned'),
                              (high_priority, u'High Priority')]:
            folder.set_handler('%s/s%s' % (name, i), search)
            kw = {'dc:title': {'en': title}}
            metadata = StoredSearch.build_metadata(**kw)
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
        """
        Returns a namespace (list of dictionaries) to be used for the
        selection box of users (the 'assigned to' field).
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
            items.sort(lambda x, y: cmp(x.get_property('dc:title'),
                                        y.get_property('dc:title')))
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
    def search_form(self, context):
        # Set Style
        css = Path(self.abspath).get_pathto('/ui/tracker/tracker.css')
        context.styles.append(str(css))

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
            namespace['search_title'] = search.get_property('dc:title')
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
                stored_search_title = stored_search.get_property('dc:title')
            except LookupError:
                pass

        if search_title and search_title != stored_search_title:
            # New Stored Search
            search_name = self.get_new_id('s')
            stored_search = StoredSearch.make_object(StoredSearch, self, search_name)

        if stored_search is None:
            # Just Search
            return context.uri.resolve(';view').replace(**context.uri.query)

        # Edit / Title
        context.commit = True
        stored_search.set_property('dc:title', search_title, 'en')
        # Edit / Search Values
        text = context.get_form_value('text').strip().lower()
        stored_search.handler.set_value('text', text)

        mtime = context.get_form_value('mtime', type=Integer)
        stored_search.handler.set_value('mtime', mtime)

        criterias = [('module', Integer), ('version', Integer),
            ('type', Integer), ('priority', Integer), ('assigned_to', String),
            ('state', Integer)]
        for name, type in criterias:
            value = context.get_form_values(name, type=type)
            stored_search.set_values(name, value, type=type)

        return context.uri.resolve(';view?search_name=%s' % search_name)


    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    def view(self, context):
        # Set Style
        css = Path(self.abspath).get_pathto('/ui/tracker/tracker.css')
        context.styles.append(str(css))

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
    export_to_csv__label__ = u'Export as CSV'
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
    change_several_bugs__label__ = u'Change several bugs'
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
            for name in ['module', 'version', 'type', 'priority', 'assigned_to',
                         'state']:
                type = History.schema[name]
                last_value = issue.get_value(name)
                new_value = context.get_form_value('change_%s' % name,type=type)
                if ((last_value==new_value) or (new_value is None) or
                    (new_value=='do_not_change')):
                    # If no modification set the last value
                    value = last_value
                else:
                    value = new_value
                if type == Unicode:
                    value = value.strip()
                record[name] = value
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
        # Send mails
        user = context.user
        if user is None:
            from_addr = ''
            user_title = self.gettext(u'ANONYMOUS')
        else:
            from_addr = user.get_property('ikaaro:email')
            user_title = user.get_title()
        template = u'--- Comment from : %s ---\n\n%s\n\n%s'
        template = self.gettext(template)
        tracker_title = self.parent.get_property('dc:title') or 'Tracker Issue'
        subject = u'[%s]' % tracker_title
        for user_id in users_issues.keys():
            user_issues = []
            for user_issue in users_issues[user_id]:
                href = user_issue['href']
                name = user_issue['name']
                title = user_issue['title']
                user_issues.append('#%s - %s - %s' %(name, title, href))
            body = template % (user_title, comment, '\n'.join(user_issues))
            to = root.get_user(user_id)
            to_addr = to.get_property('ikaaro:email')
            root.send_email(from_addr, to_addr, subject, text=body)

        # Redirect on the new search
        query = encode_query(context.uri.query)
        reference = ';view?%s&change_several_bugs=1#link' % query
        goto = context.uri.resolve(reference)
        return context.come_back(message=MSG_CHANGES_SAVED, goto=goto,
                                    keep=['ids'])


    def get_export_to_text(self, context):
        """
        Generate a text with selected records of selected issues
        """
        # Get selected columns
        selected_columns = context.get_form_values('column_selection')
        if not selected_columns:
            selected_columns = [x[0] for x in table_columns if x[0] is not 'id']
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
            id = u'#%s' % line['name']
            filtered_line.insert(0, id)
            filtered_line = u'\t'.join(filtered_line)
            tab_text.append(filtered_line)
        return u'\n'.join(tab_text)


    def get_search_results(self, context):
        """
        Method that return a list of issues that correspond to the search
        """
        error = context.check_form_input(search_fields)
        if error is not None:
            return context.come_back(error, keep=[])
        users = self.get_object('/users')
        # Choose stored Search or personalized search
        search_name = context.get_form_value('search_name')
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
        module = get_values('module', type=Integer)
        version = get_values('version', type=Integer)
        type = get_values('type', type=Integer)
        priority = get_values('priority', type=Integer)
        assign = get_values('assigned_to', type=String)
        state = get_values('state', type=Integer)
        # Execute the search
        issues = []
        now = datetime.now()
        for handler in self.search_objects(object_class=Issue):
            if text:
                if not handler.has_text(text):
                    continue
            if mtime is not None:
                if (now - handler.get_mtime()).days >= mtime:
                    continue
            if module != [] and handler.get_value('module') not in module:
                continue
            if version != [] and handler.get_value('version') not in version:
                continue
            if type != [] and handler.get_value('type') not in type:
                continue
            if priority != [] and handler.get_value('priority') not in priority:
                continue
            if assign != []:
                value = handler.get_value('assigned_to')
                if value == '':
                    value = 'nobody'
                if value not in assign:
                    continue
            if state != [] and handler.get_value('state') not in state:
                continue
            # Append
            issues.append(handler)
        return issues


    #######################################################################
    # User Interface / Add Issue
    add_form__access__ = 'is_allowed_to_edit'
    add_form__label__ = u'Add'
    def add_form(self, context):
        # Set Style
        css = Path(self.abspath).get_pathto('/ui/tracker/tracker.css')
        context.styles.append(str(css))

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

        handler = self.get_object('/ui/tracker/add_issue.xml')
        return stl(handler, namespace)


    add_issue__access__ = 'is_allowed_to_edit'
    def add_issue(self, context):
        keep = ['title', 'version', 'type', 'state', 'module', 'priority',
            'assigned_to', 'comment']
        # Check input data
        error = context.check_form_input(issue_fields)
        if error is not None:
            return context.come_back(error, keep=keep)

        # Add
        id = self.get_new_id()
        issue = Issue.make_object(Issue, self, id)
        issue._add_record(context)

        goto = context.uri.resolve2('../%s/;edit_form' % issue.name)
        return context.come_back(u'New issue addded.', goto=goto)


    go_to_issue__access__ = 'is_allowed_to_view'
    def go_to_issue(self, context):
        issue_name = context.get_form_value('issue_name')
        if not self.has_object(issue_name):
            return context.come_back(u'Issue not found.')

        issue = self.get_object(issue_name)
        if not isinstance(issue, Issue):
            return context.come_back(u'Issue not found.')

        return context.uri.resolve2('../%s/;edit_form' % issue_name)



    def update_20071119(self):
        from itools.handlers import File as BaseFile
        columns = ['id', 'title']
        for new_name in ['modules', 'types', 'priorities', 'states',
                         'versions']:
            old_name = '%s.csv' % new_name
            old_handler = BaseFile('%s/%s' %(self.handler.uri, old_name))
            if new_name == 'versions':
                columns.append('released')
                table = VersionsTable()
                metadata = Versions.build_metadata()
            else:
                table = SelectTableTable()
                metadata = SelectTable.build_metadata()
            table.update_from_csv(old_handler.to_str(), columns)
            self.handler.del_handler(old_name)
            self.handler.del_handler('%s.metadata' % old_name)
            self.handler.set_handler(new_name, table)
            self.handler.set_handler('%s.metadata' % new_name, metadata)

        # .history of each Issue
        columns = ['datetime', 'username', 'title', 'module', 'version',
                   'type', 'priority', 'assigned_to', 'state', 'comment',
                   'file']
        for issue in self.search_objects(object_class=Issue):
            old_handler = BaseFile('%s/.history' %(issue.handler.uri))
            table = History()
            table.update_from_csv(old_handler.to_str(), columns)
            issue.handler.del_handler('.history')
            issue.handler.set_handler('.history', table)


###########################################################################
# Tables
###########################################################################
class SelectTableTable(BaseTable):

    schema = {'title': Unicode}


class SelectTable(Table):

    class_id = 'tracker_select_table'
    class_handler = SelectTableTable

    def get_options(self, value=None, sort=True):
        table = self.handler
        options = [ {'id': x.id, 'title': x.title} for x in table.get_records() ]
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

        fields = self.get_fields()
        fields.insert(0, ('id', u'id'))
        fields.append(('issues', u'Issues'))
        records = []

        getter = lambda x, y: x.get_value(y)

        filter = self.name[:-1]
        if self.name.startswith('priorit'):
            filter = 'priority'

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

            count = 0
            for object in self.parent.search_objects(object_class=Issue):
                if object.get_value(filter) == id:
                    count += 1
            value = '0'
            if count != 0:
                value = '<a href="../;view?%s=%s">%s issues</a>'
                if count == 1:
                    value = '<a href="../;view?%s=%s">%s issue</a>'
                value = XMLParser(value % (filter, id, count))
            records[-1]['issues'] = value

        # Sorting
        sortby = context.get_form_value('sortby')
        sortorder = context.get_form_value('sortorder', 'up')
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



class VersionsTable(BaseTable):

    schema = {'title': Unicode(title=u'Title'),
              'released': Boolean(title=u'Released')}


class Versions(SelectTable):

    class_id = 'tracker_versions'
    class_handler = VersionsTable


###########################################################################
# Stored Searches
###########################################################################
class StoredSearch(Text):

    class_id = 'stored_search'
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
# Issues
###########################################################################
class History(BaseTable):

    schema = {'datetime': DateTime,
              'username': String,
              'title': Unicode,
              'module': Integer,
              'version': Integer,
              'type': Integer,
              'priority': Integer,
              'assigned_to': String,
              'state': Integer,
              'comment': Unicode,
              'file': String}



class Issue(Folder, VersioningAware):

    class_id = 'issue'
    class_title = u'Issue'
    class_description = u'Issue'
    class_views = [
        ['edit_form'],
        ['browse_content?mode=list'],
        ['history']]


    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        folder.set_handler('%s/.history' % name, History())


    def get_document_types(self):
        return [File]


    #######################################################################
    # API
    #######################################################################
    def get_title(self):
        return '#%s %s' % (self.name, self.get_value('title'))


    def get_history(self):
        return self.handler.get_handler('.history', cls=History)


    def get_history_records(self):
        return self.get_history().get_records()


    def get_last_history_record(self):
        history = self.handler.get_handler('.history', cls=History)
        n_records = history.get_n_records()
        if n_records == 0:
            return None
        return history.get_record(n_records - 1)


    def get_value(self, name):
        record = self.get_last_history_record()
        if record:
            return record.get_value(name)
        return None


    def _add_record(self, context):
        user = context.user
        root = context.root
        parent = self.parent
        users = root.get_object('users')

        record = {}
        # Datetime
        record['datetime'] = datetime.now()
        # User XXX
        if user is None:
            record['username'] = ''
        else:
            record['username'] = user.name
        # Title
        title = context.get_form_value('title', type=Unicode).strip()
        record['title'] = title
        # Version, Priority, etc.
        for name in ['module', 'version', 'type', 'priority', 'assigned_to',
                     'state', 'comment']:
            type = History.schema[name]
            value = context.get_form_value(name, type=type)
            if type == Unicode:
                value = value.strip()
            record[name] = value
        # Files XXX
        file = context.get_form_value('file')
        if file is None:
            record['file'] = ''
        else:
            filename, mimetype, body = file
            # Upload
            # The mimetype sent by the browser can be minimalistic
            guessed = mimetypes.guess_type(filename)[0]
            if guessed is not None:
                mimetype = guessed
            # Find a non used name
            filename = checkid(filename)
            filename = generate_name(filename, self.get_names())
            record['file'] = filename
            # Set the handler
            cls = get_object_class(mimetype)
            handler = cls.class_handler(string=body)
            metadata = cls.build_metadata()
            self.handler.set_handler(filename, handler)
            self.handler.set_handler('%s.metadata' % filename, metadata)
        # Update
        modifications = self.get_diff_with(record, context)
        history = self.get_history()
        history.add_record(record)
        # Send a Notification Email
        # Notify / From
        if user is None:
            from_addr = ''
            user_title = self.gettext(u'ANONYMOUS')
        else:
            from_addr = user.get_property('ikaaro:email')
            user_title = user.get_title()
        # Notify / To
        to_addrs = set()
        reported_by = self.get_reported_by()
        if reported_by:
            to_addrs.add(reported_by)
        assigned_to = self.get_value('assigned_to')
        if assigned_to:
            to_addrs.add(assigned_to)
        if user.name in to_addrs:
            to_addrs.remove(user.name)
        # Notify / Subject
        tracker_title = self.parent.get_property('dc:title') or 'Tracker Issue'
        subject = '[%s #%s] %s' % (tracker_title, self.name, title)
        # Notify / Body
        if context.object.class_id == Tracker.class_id:
            uri = context.uri.resolve('%s/;edit_form' % self.name)
        else:
            uri = context.uri.resolve(';edit_form')
        body = '#%s %s %s\n\n' % (self.name, self.get_value('title'), str(uri))
        body += self.gettext(u'The user %s did some changes.') % user_title
        body += '\n\n'
        if file:
            body += self.gettext(u'  New Attachment: %s') % filename + '\n'
        comment = context.get_form_value('comment', type=Unicode)
        if comment:
            body += self.gettext(u'Comment') + u'\n'
            body += u'-------\n\n'
            body += comment + u'\n\n'
            body += u'-------\n\n'
        if modifications:
            body += modifications
        # Notify / Send
        for to_addr in to_addrs:
            to_addr = users.get_object(to_addr)
            to_addr = to_addr.get_property('ikaaro:email')
            root.send_email(from_addr, to_addr, subject, text=body)


    def get_diff_with(self, record, context):
        """Return a text with the diff between the last and new issue state"""
        root = context.root
        modifications = []
        history = self.get_history()
        if history.get_n_records() > 0:
            # Edit issue
            template = self.gettext(u'%s: %s to %s')
        else:
            # New issue
            template = self.gettext(u'%s: %s%s')
        # Modification of title
        last_title = self.get_value('title') or ''
        new_title = record['title']
        if last_title != new_title:
            title = self.gettext(u'Title')
            modifications.append(template %(title, last_title, new_title))
        # List modifications
        for key in [(u'Module', 'module', 'modules'),
                    (u'Version', 'version', 'versions'),
                    (u'Type', 'type', 'types'),
                    (u'Priority', 'priority', 'priorities'),
                    (u'State', 'state', 'states')]:
            title, name, csv_name = key
            title = self.gettext(title)
            new_value = record[name]
            last_value = self.get_value(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = u''
            csv = self.parent.get_object(csv_name).handler
            if last_value:
                last_title = csv.get_record(last_value).title
            if new_value:
                new_title = csv.get_record(new_value).title
            text = template % (title, last_title, new_title)
            modifications.append(text)

        # Modifications of assigned_to
        last_user = self.get_value('assigned_to')
        new_user = record['assigned_to']
        if last_user and last_user!=new_user:
            last_user = root.get_user(last_user)
            if last_user:
                last_user = last_user.get_property('ikaaro:email')
            new_user = root.get_user(new_user).get_property('ikaaro:email')
            title = self.gettext(u'Assigned to')
            modifications.append(template  %(title, last_user, new_user))

        return u'\n'.join(modifications)


    def get_reported_by(self):
        history = self.get_history()
        return history.get_record(0).username


    def get_informations(self):
        """
        Construct a dict with issue informations.
        This dict is used to construct a line for a table.
        """
        parent = self.parent
        tables = {'module': parent.get_object('modules'),
                  'version': parent.get_object('versions'),
                  'type': parent.get_object('types'),
                  'priority': parent.get_object('priorities'),
                  'state': parent.get_object('states')}
        infos = {'name': self.name,
                 'id': int(self.name),
                 'title': self.get_value('title')}
        for name in 'module', 'version', 'type', 'priority', 'state':
            value = self.get_value(name)
            if value is not None:
                record = tables[name].handler.get_record(int(value))
                infos[name] = record and record.title or None
            else:
                infos[name] = None

        assigned_to = self.get_value('assigned_to')
        # solid in case the user has been removed
        users = self.get_object('/users')
        if assigned_to and users.has_object(assigned_to):
                user = users.get_object(assigned_to)
                infos['assigned_to'] = user.get_title()
        else:
            infos['assigned_to'] = ''
        infos['comment'] = self.get_value('comment')
        infos['mtime'] = format_datetime(self.get_mtime())
        infos['mtime_sort'] = self.get_mtime()
        return infos


    def get_comment(self):
        records = self.get_history_records()
        i = len(records) - 1
        while i >= 0:
            record = records[i]
            comment = record.comment
            if comment:
                return comment
            i -= 1
        return ''


    def has_text(self, text):
        if text in self.get_value('title').lower():
            return True
        return text in self.get_comment().lower()


    def indent(self, text):
        """ Replace spaces at the beginning of a line by &nbsp;
            Replace '\n' by <br>\n and URL by HTML links
            Fold lines (with spaces) to 150c.
        """
        res = []
        text = text.encode('utf-8')
        text = XML.encode(text)
        for line in text.splitlines():
            sline = line.lstrip()
            indent = len(line) - len(sline)
            if indent:
                line = '&nbsp;' * indent + sline
            if len(line) < 150:
                line = sub('http://(.\S*)', r'<a href="http://\1">\1</a>', line)
                res.append(line)
            else:
                # Fold lines to 150c
                text = line.split()
                line = ''
                while text != []:
                    word = text.pop(0)
                    if len(word) + len(line) > 150:
                        line = sub('http://(.\S*)',
                                   r'<a href="http://\1">\1</a>', line)
                        res.append(line)
                        line = ''
                    line = line + word + ' '
                if line != '':
                    line = sub('http://(.\S*)', r'<a href="http://\1">\1</a>',
                               line)
                    res.append(line)
        return XMLParser('\n'.join(res))


    #######################################################################
    # User Interface
    #######################################################################
    edit_form__access__ = 'is_allowed_to_edit'
    edit_form__label__ = u'Edit'
    def edit_form(self, context):
        # Set Style & JS
        abspath = Path(self.abspath) 
        css = abspath.get_pathto('/ui/tracker/tracker.css')
        context.styles.append(str(css))
        js = abspath.get_pathto('/ui/tracker/tracker.js')
        context.scripts.append(str(js))

        # Local variables
        users = self.get_object('/users')
        values = self.get_last_history_record()
        # XXX
        title = values.title
        module = values.module
        version = values.version
        type = values.type
        priority = values.priority
        assigned_to = values.assigned_to
        state = values.state
        comment = values.comment
        file = values.file

        # Build the namespace
        namespace = {}
        namespace['number'] = self.name
        namespace['title'] = title
        # Reported by
        reported_by = self.get_reported_by()
        reported_by = users.get_object(reported_by)
        namespace['reported_by'] = reported_by.get_title()
        # Topics, Version, Priority, etc.
        get = self.parent.get_object
        namespace['modules'] = get('modules').get_options(module)
        namespace['versions'] = get('versions').get_options(version)
        namespace['types'] = get('types').get_options(type)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        namespace['states'] = get('states').get_options(state, sort=False)
        # Assign To
        namespace['users'] = self.parent.get_members_namespace(assigned_to)
        # Date Start / Date End
        namespace['start_date'] = None
        namespace['start_time'] = None
        namespace['end_date'] = None
        namespace['end_time'] = None
        # Comments
        comments = []
        i = 0
        for record in self.get_history_records():
            comment = record.comment
            file = record.file
            if not comment and not file:
                continue
            datetime = record.datetime
            # solid in case the user has been removed
            username = record.username
            user_title = username
            if users.has_object(username):
                user_title = users.get_object(username).get_title()
            i += 1
            comments.append({
                'number': i,
                'user': user_title,
                'datetime': format_datetime(datetime),
                'comment': self.indent(comment),
                'file': file})
        comments.reverse()
        namespace['comments'] = comments

        handler = self.get_object('/ui/tracker/edit_issue.xml')
        return stl(handler, namespace)


    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context):
        # Check input data
        error = context.check_form_input(issue_fields)
        if error is not None:
            return context.come_back(error)
        # Edit
        self._add_record(context)

        return context.come_back(MSG_CHANGES_SAVED)


    #######################################################################
    # User Interface / History
    history__access__ = 'is_allowed_to_view'
    history__label__ = u'History'
    def history(self, context):
        # Set Style
        css = Path(self.abspath).get_pathto('/ui/tracker/tracker.css')
        context.styles.append(str(css))

        # Local variables
        users = self.get_object('/users')
        versions = self.get_object('../versions')
        types = self.get_object('../types')
        states = self.get_object('../states')
        modules = self.get_object('../modules')
        priorities = self.get_object('../priorities')
        # Initial values
        previous_title = None
        previous_version = None
        previous_type = None
        previous_state = None
        previous_module = None
        previous_priority = None
        previous_assigned_to = None

        # Build the namespace
        namespace = {}
        namespace['number'] = self.name
        rows = []
        i = 0
        for record in self.get_history_records():
            datetime = record.datetime
            username = record.username
            title = record.title
            module = record.module
            version = record.version
            type = record.type
            priority = record.priority
            assigned_to = record.assigned_to
            state = record.state
            comment = record.comment
            file = record.file
            # solid in case the user has been removed
            user_exist = users.has_object(username)
            usertitle = (user_exist and
                         users.get_object(username).get_title() or username)
            comment = XML.encode(Unicode.encode(comment))
            comment = XMLParser(comment.replace('\n', '<br />'))
            i += 1
            row_ns = {'number': i,
                      'user': usertitle,
                      'datetime': format_datetime(datetime),
                      'title': None,
                      'version': None,
                      'type': None,
                      'state': None,
                      'module': None,
                      'priority': None,
                      'assigned_to': None,
                      'comment': comment,
                      'file': file}

            if title != previous_title:
                previous_title = title
                row_ns['title'] = title
            if version != previous_version:
                previous_version = version
                if module is None:
                    row_ns['version'] = ' '
                else:
                    version = versions.handler.get_record(int(version))
                    row_ns['version'] = version.get_value('title')
            if type != previous_type:
                previous_type = type
                if type is None:
                    row_ns['type'] = ' '
                else:
                    type = types.handler.get_record(int(type))
                    row_ns['type'] = type.get_value('title')
            if state != previous_state:
                previous_state = state
                if state is None:
                    row_ns['state'] = ' '
                else:
                    state = states.handler.get_record(int(state))
                    row_ns['state'] = state.get_value('title')
            if module != previous_module:
                previous_module = module
                if module is None:
                    row_ns['module'] = ' '
                else:
                    module = modules.handler.get_record(int(module))
                    row_ns['module'] = module.get_value('title')
            if priority != previous_priority:
                previous_priority = priority
                if priority is None:
                    row_ns['priority'] = ' '
                else:
                    priority = priorities.handler.get_record(int(priority))
                    row_ns['priority'] = priority.get_value('title')
            if assigned_to != previous_assigned_to:
                previous_assigned_to = assigned_to
                if assigned_to and users.has_object(assigned_to):
                    assigned_to_user = users.get_object(assigned_to)
                    row_ns['assigned_to'] = assigned_to_user.get_title()
                else:
                    row_ns['assigned_to'] = ' '

            rows.append(row_ns)

        rows.reverse()
        namespace['rows'] = rows

        handler = self.get_object('/ui/tracker/issue_history.xml')
        return stl(handler, namespace)


    def get_size(self):
        # FIXME Used by VersioningAware to define the size of the document
        return 0


###########################################################################
# Register
###########################################################################
register_object_class(Tracker)
register_object_class(Issue)
register_object_class(SelectTable)
register_object_class(Versions)
register_object_class(StoredSearch)
