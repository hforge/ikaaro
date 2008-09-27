# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
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
from copy import deepcopy
from datetime import datetime
from operator import itemgetter

# Import from itools
from itools.csv import CSVFile
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import merge_dics
from itools.stl import stl
from itools.uri import encode_query, Reference
from itools.web import BaseView, BaseForm, STLForm, get_context
from itools.web import INFO, ERROR

# Import from ikaaro
from ikaaro.datatypes import CopyCookie
from ikaaro.exceptions import ConsistencyError
from ikaaro import messages
from ikaaro.views import BrowseForm, SearchForm as BaseSearchForm, ContextMenu
from issue import Issue, issue_fields
from stored import StoredSearch


columns = [
    ('id', MSG(u'Id')),
    ('title', MSG(u'Title')),
    ('version', MSG(u'Version')),
    ('module', MSG(u'Module')),
    ('type', MSG(u'Type')),
    ('priority', MSG(u'Priority')),
    ('state', MSG(u'State')),
    ('assigned_to', MSG(u'Assigned To')),
    ('mtime', MSG(u'Modified'))]



class GoToIssueMenu(ContextMenu):

    title = MSG(u'Go To Issue')
    template = '/ui/tracker/menu_goto.xml'

    def get_namespace(self, resource, context):
        return {'title': self.title}



class StoreSearchMenu(ContextMenu):
    """Form to store a search.
    """

    title = MSG(u'Remember this search')
    template = '/ui/tracker/menu_remember.xml'

    def get_namespace(self, resource, context):
        name = context.get_query_value('search_name')
        if name:
            search = resource.get_resource(name)
            search_title = search.get_title()
        else:
            search_title = None

        return {
            'title': self.title,
            'search_name': name,
            'search_title': search_title}



class StoredSearchesMenu(ContextMenu):
    """Provides links to every stored search.
    """

    title = MSG(u'Stored Searches')

    def get_items(self, resource, context):
        # If called from a child
        if isinstance(resource, Issue):
            resource = resource.parent

        # Namespace
        search_name = context.get_query_value('search_name')
        base = '/%s/;view' % context.site_root.get_pathto(resource)
        items = resource.search_resources(cls=StoredSearch)
        items = [
            {'title': x.get_property('title'),
             'href': '%s?search_name=%s' % (base, x.name),
             'class': 'nav_active' if (x.name == search_name) else None}
            for x in items ]
        items.sort(lambda x, y: cmp(x['title'], y['title']))

        return items



class TrackerAddIssue(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Add')
    icon = 'new.png'
    template = '/ui/tracker/add_issue.xml'

    schema = issue_fields


    def get_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Build the namespace
        namespace = {}
        namespace['title'] = context.get_form_value('title', type=Unicode)
        namespace['comment'] = context.get_form_value('comment', type=Unicode)
        # Others
        get = resource.get_resource
        module = context.get_form_value('module', type=Integer)
        namespace['modules'] = get('modules').get_options(module)
        version = context.get_form_value('version', type=Integer)
        namespace['versions'] = get('versions').get_options(version)
        type = context.get_form_value('type', type=Integer)
        namespace['types'] = get('types').get_options(type)
        priority = context.get_form_value('priority', type=Integer)
        namespace['priorities'] = get('priorities').get_options(priority)
        state = context.get_form_value('state', type=Integer)
        namespace['states'] = get('states').get_options(state)

        users = resource.get_resource('/users')
        assigned_to = context.get_form_values('assigned_to', type=String)
        namespace['users'] = resource.get_members_namespace(assigned_to)

        namespace['cc_add'] = resource.get_members_namespace(())

        return namespace


    def action(self, resource, context, form):
        # Add
        id = resource.get_new_id()
        issue = Issue.make_resource(Issue, resource, id)
        issue._add_record(context, form)

        # Ok
        message = INFO(u'New issue added.')
        goto = './%s/' % id
        return context.come_back(message, goto=goto)



class TrackerView(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'
    template = '/ui/tracker/view_tracker.xml'

    schema = {
        'ids': String(multiple=True, mandatory=True)}

    tracker_schema = {
        # search_fields
        'search_name': Unicode(),
        'mtime': Integer(default=0),
        'module': Integer(multiple=True, default=()),
        'version': Integer(multiple=True, default=()),
        'type': Integer(multiple=True, default=()),
        'priority': Integer(multiple=True, default=()),
        'assigned_to': String(multiple=True, default=()),
        'state': Integer(multiple=True, default=()),
        # Specific fields
        'export_to_text': Boolean,
        'export_to_csv': Boolean,
        'change_several_bugs': Boolean,
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        # BrowseForm fields
        'sort_by': String(multiple=True, default=['title']),
    }

    context_menus = [StoreSearchMenu()]


    def get_query_schema(self):
        return merge_dics(BrowseForm.get_query_schema(self),
                          self.tracker_schema)


    def get_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        namespace = BrowseForm.get_namespace(self, resource, context)
        namespace['method'] = 'GET'
        namespace['action'] = '.'
        # Set title of search
        query = context.query
        search_name = query['search_name']
        if search_name:
            search = resource.get_resource(search_name)
            title = search.get_title()
        else:
            title = None
#        nb_results = len(lines)
        namespace['nb_results'] = 'XXX'
        namespace['title'] = title
        # Keep the search_parameters, clean different actions
        query_params = deepcopy(context.uri.query)
        params = {}
        for key in query_params:
            if not key.startswith(';'):
                params[key] = query_params[key]
        params = encode_query(params)
        params = params.replace('change_several_bugs=1', '')
        params = params.replace('export_to_csv=1', '')
        params = params.replace('export_to_text=1', '')
        params = params.replace('&&', '&').replace('?&', '?').replace('&#', '#')
        namespace['search_parameters'] = params
        criteria = []
        for key in ['search_name', 'mtime']:
            value = query[key]
            criteria.append({'name': key, 'value': value})
        keys = 'module', 'version', 'type', 'priority', 'assigned_to', 'state'
        for key in keys:
            for value in query[key]:
                criteria.append({'name': key, 'value': value})
        namespace['criteria'] = criteria


        return namespace


    def get_items(self, resource, context):
        return resource.get_search_results(context)


    # XXX Copied from folder_views except Adjust sorting
    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        # Adjust Sorting
        if sort_by == 'mtime':
            sort_by = 'mtime_sort'
        elif sort_by in ('priority', 'state'):
            sort_by = '%s_rank' % sort_by
        elif sort_by:
            sort_by = sort_by[0]
        items = results.get_documents(sort_by=sort_by, reverse=reverse,
                                      start=start, size=size)

        # Access Control (FIXME this should be done before batch)
        user = context.user
        root = context.root
        allowed_items = []
        for item in items:
            item = root.get_resource(item.abspath)
            ac = item.get_access_control()
            if ac.is_allowed_to_view(user, item):
                allowed_items.append(item)

        return allowed_items


    def get_item_value(self, resource, context, item, column):
        if column in ('checkbox', 'checked'):
            # Show checkbox or not
            show_checkbox = False
            query = context.query
            if (query['export_to_text'] or query['export_to_csv'] or
                query['change_several_bugs']):
                show_checkbox = True
            if column == 'checkbox':
                return show_checkbox
            selected_issues = context.get_form_values('ids')
            if not selected_issues:
                return True
            else:
                if item.name in selected_issues:
                    return item.name
                    ##return issue.name, False ???

        line = item.get_informations()
        if column == 'title':
            # Add link to title
            link = '%s/;edit' % item.name
            return (line['title'], link)
        if column in line:
            return line[column]


    def get_actions(self, resource, context, items):
        if len(items) == 0:
            return []

        return []
        # XXX
        ac = resource.get_access_control()
        if ac.is_allowed_to_edit(context.user, resource):
            return [('remove', u'Remove', 'button_delete',None)]

        return []


    def get_table_columns(self, resource, context):
        return columns



class TrackerSearch(BaseSearchForm, TrackerView):

    access = 'is_allowed_to_view'
    title = MSG(u'Search')
    icon = 'search.png'

    # Search Form
    search_template = '/ui/tracker/search.xml'
    search_schema = {
        'search_name': Unicode(),
        'search_title': Unicode(),
        'text': Unicode(),
        'mtime': Integer(),
        'module': Integer(multiple=True),
        'version': Integer(multiple=True),
        'type': Integer(multiple=True),
        'priority': Integer(multiple=True),
        'assigned_to': String(multiple=True),
        'state': Integer(multiple=True),
        }


    def get_search_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Search Form
        get_resource = resource.get_resource
        query = context.query
        search_name = query['search_name']
        if search_name:
            search = get_resource(search_name)
            get_value = search.handler.get_value
            get_values = search.get_values
            search_title = search.get_property('title')
        else:
            get_value = query.get
            get_values = query.get
            search_name = None
            search_title = query['search_title']

        # Build the namespace
        module = get_values('module')
        type = get_values('type')
        version = get_values('version')
        priority = get_values('priority')
        assign = get_values('assigned_to')
        state = get_values('state')

        # is_admin
        ac = resource.get_access_control()
        pathto_website = resource.get_pathto(resource.get_site_root())
        return {
            'search_name': search_name,
            'search_title': search_title,
            'text': get_value('text'),
            'mtime': get_value('mtime'),
            'modules': get_resource('modules').get_options(module),
            'types': get_resource('types').get_options(type),
            'versions': get_resource('versions').get_options(version),
            'priorities': get_resource('priorities').get_options(priority),
            'states': get_resource('states').get_options(state),
            'users': resource.get_members_namespace(assign, True),
            'is_admin': ac.is_admin(context.user, resource),
            'manage_assigned': '%s/;permissions' % pathto_website,
        }


    def get_namespace(self, resource, context):
        namespace = BaseSearchForm.get_namespace(self, resource, context)
        namespace['batch'] = None
        namespace['table'] = None
        return namespace



class TrackerRememberSearch(BaseForm):

    access = 'is_allowed_to_edit'
    schema = {
        'search_name': String,
        'search_title': Unicode(mandatory=True)}


    def GET(self, resource, context):
        # Required for when the form fails the automatic checks
        return context.come_back(message=context.message)


    def action(self, resource, context, form):
        name = form['search_name']
        if name is None:
            # New search
            name = resource.get_new_id('s')
            search = StoredSearch.make_resource(StoredSearch, resource, name)
            message = MSG(u'The search has been stored.')
        else:
            search = resource.get_resource(name)
            message = MSG(u'The search title has been changed.')

        # Set title
        title = form['search_title']
        search.set_property('title', title)

        # Go
        return context.come_back(message, goto=';view?search_name=%s' % name)



class TrackerStoredSearches(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Stored Searches')
    template = '/ui/tracker/stored_searches.xml'
    schema = {
        'ids': String(multiple=True, mandatory=True),
    }


    def get_namespace(self, resource, context):
        stored_searches = [
            {'name': x.name, 'title': x.get_title()}
            for x in resource.search_resources(cls=StoredSearch) ]
        stored_searches.sort(key=itemgetter('title'))

        return {'stored_searches': stored_searches}


    def action(self, resource, context, form):
        # FIXME This is a simplified version of 'BrowseContent.remove'
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Remove resources
        removed = []
        not_removed = []
        abspath = resource.get_abspath()

        for name in ids:
            try:
                resource.del_resource(name)
            except ConsistencyError:
                not_removed.append(name)
                continue
            removed.append(name)
            # Clean cookie
            if str(abspath.resolve2(name)) in paths:
                context.del_cookie('ikaaro_cp')
                paths = []

        if removed:
            resources = ', '.join(removed)
            message = messages.MSG_RESOURCES_REMOVED(resources=resources)
            context.message = message
        else:
            context.message = messages.MSG_NONE_REMOVED



class TrackerGoToIssue(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        issue_name = context.get_form_value('issue_name')
        if not issue_name:
            return context.come_back(messages.MSG_NAME_MISSING)

        if not resource.has_resource(issue_name):
            return context.come_back(ERROR(u'Issue not found.'))

        issue = resource.get_resource(issue_name)
        if not isinstance(issue, Issue):
            return context.come_back(ERROR(u'Issue not found.'))

        return context.uri.resolve2('../%s/;edit' % issue_name)



class TrackerExportToText(TrackerView):

    template = '/ui/tracker/export_to_text.xml'

    def get_query_schema(self):
        return merge_dics(TrackerView.get_query_schema(self),
                          ids=String(multiple=True, default=[]),
                          column_selection=String(multiple=True,
                                                  default=['title']))


    def get_namespace(self, resource, context):
        namespace = TrackerView.get_namespace(self, resource, context)

        # Column Selector
        selection = context.query['column_selection']
        export_columns = columns[2:] + [columns[1]]
        namespace['columns'] = [
            {'name': name, 'title': title, 'checked': name in selection}
            for name, title in export_columns ]

        # Text
        items = self.get_items(resource, context)
        items = self.sort_and_batch(resource, context, items)
        selected_items = context.query['ids']
        if selected_items:
            items = [ x for x in items if x.name in selected_items ]
        items = [ x.get_informations() for x in items ]
        # Create the text
        lines = []
        for item in items:
            name = item['name']
            line = [u'#%s' % name] + [ unicode(item[x]) for x in selection ]
            line = u'\t'.join(line)
            lines.append(line)
        namespace['text'] = u'\n'.join(lines)

        # Ok
        return namespace



class TrackerExportToCSVForm(TrackerView):

    template = '/ui/tracker/export_to_csv.xml'



class TrackerExportToCSV(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u'Export to CSV')
    query_schema = {
        'editor': String(default='excel'),
        'ids': String(multiple=True),
    }

    def GET(self, resource, context):
        # Get search results
        results = resource.get_search_results(context)
        if isinstance(results, Reference):
            return results

        # Selected issues
        issues = results.get_documents()
        selected_issues = context.query['ids']
        if selected_issues:
            issues = [ x for x in issues if x.name in selected_issues ]

        if len(issues) == 0:
            context.message = ERROR(u"No data to export.")
            return

        # Get CSV encoding and separator (OpenOffice or Excel)
        editor = context.query['editor']
        if editor == 'oo':
            separator = ','
            encoding = 'utf-8'
        else:
            separator = ';'
            encoding = 'cp1252'

        # Create the CSV
        csv = CSVFile()
        for issue in issues:
            issue = resource.get_resource(issue.name)
            issue = issue.get_informations()
            row = []
            for name, label in columns:
                value = issue[name]
                if isinstance(value, unicode):
                    value = value.encode(encoding)
                else:
                    value = str(value)
                row.append(value)
            csv.add_row(row)

        # Set response type
        response = context.response
        response.set_header('Content-Type', 'text/comma-separated-values')
        response.set_header('Content-Disposition',
                            'attachment; filename=export.csv')
        return csv.to_str(separator=separator)



class TrackerChangeSeveralBugs(TrackerView):

    access = 'is_allowed_to_view'
    title = MSG(u'Change Several Issues')
    template = '/ui/tracker/change_bugs.xml'
    schema = {
        'comment': Unicode,
        'ids': String(multiple=True),
        'change_module': Integer,
        'change_version': Integer,
        'change_type': Integer,
        'change_priority': Integer,
        'change_assigned_to': String,
        'change_state': Integer,
    }


    def get_namespace(self, resource, context):
        namespace = TrackerView.get_namespace(self, resource, context)
        # Edit several bugs at once
        get_resource = resource.get_resource
        namespace['modules'] = get_resource('modules').get_options()
        namespace['versions'] = get_resource('versions').get_options()
        namespace['priorities'] = get_resource('priorities').get_options()
        namespace['types'] = get_resource('types').get_options()
        namespace['states'] = get_resource('states').get_options()
        users = resource.get_resource('/users')
        namespace['users'] = resource.get_members_namespace('')

        # Ok
        return namespace


    def action(self, resource, context, form):
        # Get search results
        results = resource.get_search_results(context)
        if isinstance(results, Reference):
            return results

        # Selected issues
        issues = results.get_documents()
        selected_issues = form['ids']
        if selected_issues:
            issues = [ x for x in issues if x.name in selected_issues ]

        if len(issues) == 0:
            context.message = ERROR(u"No data to export.")
            return

        # Modify all issues selected
        comment = form['comment']
        user = context.user
        username = user and user.name or ''
        users_issues = {}
        for issue in issues:
            issue = resource.get_resource(issue.name)
            # Create a new record
            record = {
                'datetime': datetime.now(),
                'username': username,
                'title': issue.get_value('title'),
                'cc_list': issue.get_value('cc_list'),
                'file': '',
            }
            # Assign-To
            assigned_to = issue.get_value('assigned_to')
            new_assigned_to = form['change_assigned_to']
            if new_assigned_to == 'do-not-change':
                record['assigned_to'] = assigned_to
            else:
                record['assigned_to'] = new_assigned_to
            # Integer Fields
            for name in 'module', 'version', 'type', 'priority', 'state':
                new_value = form['change_%s' % name]
                if new_value == -1:
                    record[name] = issue.get_value(name)
                else:
                    record[name] = new_value
            # Comment
            record['comment'] = comment
            modifications = issue.get_diff_with(record, context)
            if modifications:
                title = MSG(u'Modifications:').gettext()
                record['comment'] += u'\n\n%s\n\n%s' % (title, modifications)

            # Save issue
            history = issue.handler.get_handler('.history')
            history.add_record(record)
            # Mail (create a dict with a list of issues for each user)
            info = {'href': context.uri.resolve(issue.name),
                    'name': issue.name,
                    'title': issue.get_title()}
            if new_assigned_to and new_assigned_to != 'do-not-change':
                users_issues.setdefault(new_assigned_to, []).append(info)
            if assigned_to and assigned_to != new_assigned_to:
                users_issues.setdefault(assigned_to, []).append(info)
            # Change
            context.server.change_resource(issue)

        # Send mails
        root = context.root
        if user is None:
            user_title = MSG(u'ANONYMOUS').gettext()
        else:
            user_title = user.get_title()
        template = MSG(u'--- Comment from: $user ---\n\n$comment\n\n$issues')
        tracker_title = resource.get_property('title') or 'Tracker Issue'
        subject = u'[%s]' % tracker_title
        for user_id in users_issues:
            user_issues = [
                u'#%s - %s - %s' % (x['href'], x['name'], x['title'])
                for x in users_issues[user_id]
            ]
            user_issues = '\n'.join(user_issues)
            body = template.gettext(user=user_title, comment=comment,
                                    issues=user_issues)
            to_addr = root.get_user(user_id).get_property('email')
            root.send_email(to_addr, subject, text=body)

        # Redirect on the new search
        query = encode_query(context.uri.query)
        reference = ';view?%s&change_several_bugs=1#link' % query
        goto = context.uri.resolve(reference)

        keys = context.get_form_keys()
        keep = ['search_name', 'mtime', 'module', 'version', 'type',
                'priority', 'assigned_to', 'state']
        keep = [ x for x in keep if x in keys]
        return context.come_back(messages.MSG_CHANGES_SAVED, goto=goto,
                                 keep=keep)

