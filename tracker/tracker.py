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
from datetime import datetime, timedelta
from operator import itemgetter
from string import Template

# Import from itools
from itools.csv import CSVFile
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import ConfigFile as BaseConfigFile
from itools.stl import stl
from itools.uri import encode_query, Reference
from itools.web import BaseView, BaseForm, STLForm, get_context
from itools.xapian import EqQuery, RangeQuery, AndQuery, OrQuery, PhraseQuery

# Import from ikaaro
from ikaaro.datatypes import CopyCookie
from ikaaro.exceptions import ConsistencyError
from ikaaro.folder import Folder
from ikaaro.messages import MSG_NONE_REMOVED, MSG_OBJECTS_REMOVED
from ikaaro.messages import MSG_NAME_MISSING, MSG_CHANGES_SAVED
from ikaaro.registry import register_object_class
from ikaaro.text import Text
from ikaaro.views import BrowseForm, SearchForm as BaseSearchForm, ContextMenu
from issue import History, Issue, issue_fields
from resources import Resources
from tables import SelectTableTable, SelectTable
from tables import OrderedSelectTableTable, OrderedSelectTable
from tables import Versions, VersionsTable


resolution = timedelta.resolution


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



class StoredSearchesMenu(ContextMenu):

    title = MSG(u'Stored Searches')

    def get_items(self, resource, context):
        # If called from a child
        if isinstance(resource, Issue):
            resource = resource.parent

        # Namespace
        base = '/%s/;view' % context.site_root.get_pathto(resource)
        items = resource.search_objects(object_class=StoredSearch)
        items = [
            {'title': x.get_property('title'),
             'href': '%s?search_name=%s' % (base, x.name)}
            for x in items ]
        items.sort(lambda x, y: cmp(x['title'], y['title']))

        return items



###########################################################################
# Views
###########################################################################

class AddIssueForm(STLForm):

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
        issue = Issue.make_object(Issue, resource, id)
        issue._add_record(context, form)

        # Ok
        message = MSG(u'New issue added.')
        goto = './%s/' % id
        return context.come_back(message, goto=goto)



class View(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'
    template = '/ui/tracker/view_tracker.xml'

    schema = {
        'ids': String(multiple=True, mandatory=True),
    }

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


    def view__sublabel__(self, **kw):
        search_name = kw.get('search_name')
        if search_name is None:
            return None
        resource = get_context().resource
        search = resource.get_resource(search_name)
        return search.get_title()


    def get_query_schema(self):
        schema = BrowseForm.get_query_schema(self)
        schema.update(self.tracker_schema)
        return schema


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
            title = MSG(u'View Tracker').gettext()
##        nb_results = len(lines)
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

        # Export_to_text
        namespace['export_to_text'] = False
        if query['export_to_text']:
            namespace['method'] = 'GET'
            namespace['action'] = ';view'
            namespace['export_to_text'] = True
            namespace['columns'] = []
            # List columns
            column_select = context.get_form_values('column_selection',
                                                    default=['title'])
            # Use columns in a different order and without the id
            export_columns = columns[2:] + [columns[1]]
            for name, title in export_columns:
                namespace['columns'].append({'name': name, 'title': title,
                                             'checked': name in columns})
            namespace['text'] = resource.get_export_to_text(context)
        # Export_to_csv
        namespace['export_to_csv'] = False
        if query['export_to_csv']:
            namespace['export_to_csv'] = True
            namespace['method'] = 'GET'
            namespace['action'] = ';export_to_csv'
        # Edit several bugs at once
        namespace['change_several_bugs'] = False
        if query['change_several_bugs']:
            get = resource.get_resource
            namespace['method'] = 'POST'
            namespace['action'] = ';change_several_bugs'
            namespace['change_several_bugs'] = True
            namespace['modules'] = get('modules').get_options()
            namespace['versions'] = get('versions').get_options()
            namespace['priorities'] = get('priorities').get_options()
            namespace['types'] = get('types').get_options()
            namespace['states'] = get('states').get_options()
            users = resource.get_resource('/users')
            namespace['users'] = resource.get_members_namespace('')

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


    def xget_namespace(self, resource, context):

        namespace = {}
        namespace['method'] = 'GET'
        namespace['action'] = '.'
        # Get search results
        query = context.query
        results = resource.get_search_results(context, query)
        # Analyse the result
        if isinstance(results, Reference):
            return results
##        # Selected issues
##        selected_issues = context.get_form_values('ids')
##        # Show checkbox or not
##        show_checkbox = False
##        if (query['export_to_text'] or query['export_to_csv'] or
##            query['change_several_bugs']):
##            show_checkbox = True
##        # Construct lines
##        lines = []
##        for issue in results:
##            line = issue.get_informations()
##            # Add link to title
##            link = '%s/;edit' % issue.name
##            line['title'] = (line['title'], link)
##            if show_checkbox:
##                line['checkbox'] = True
##                if not selected_issues:
##                    line['checked'] = True
##                else:
##                    if issue.name in selected_issues:
##                        line['checked'] = issue.name
##            lines.append(line)
        # Sort
##        sortby = query['sortby']
##        sortorder = query['sortorder']
##        if sortby == 'mtime':
##            lines.sort(key=itemgetter('mtime_sort'))
##        elif sortby in ('priority', 'state'):
##            lines.sort(key=itemgetter('%s_rank' % sortby))
##        else:
##            lines.sort(key=itemgetter(sortby[0]))
##        if sortorder == 'down':
##            lines.reverse()
        # Set title of search
        search_name = query['search_name']
        if search_name:
            search = resource.get_resource(search_name)
            title = search.get_title()
        else:
            title = MSG(u'View Tracker').gettext()
        nb_results = len(lines)
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
##        # Table
##        batch = Batch(size=nb_results, msg_1=MSG(u'There is 1 result.'),
##                      msg_2=MSG(u'There are ${n} results.'))
##        namespace['batch'] = batch.render(0, nb_results, context)
##        namespace['table'] = table(columns, lines, [sortby], sortorder,
##                                   actions=actions, table_with_form=False)
        namespace['nb_results'] = nb_results
        # Export_to_text
        namespace['export_to_text'] = False
        if query['export_to_text']:
            namespace['method'] = 'GET'
            namespace['action'] = ';view'
            namespace['export_to_text'] = True
            namespace['columns'] = []
            # List columns
            column_select = context.get_form_values('column_selection',
                                                    default=['title'])
            # Use columns in a different order and without the id
            export_columns = columns[2:] + [columns[1]]
            for name, title in export_columns:
                namespace['columns'].append({'name': name, 'title': title,
                                             'checked': name in columns})
            namespace['text'] = resource.get_export_to_text(context)
        # Export_to_csv
        namespace['export_to_csv'] = False
        if query['export_to_csv']:
            namespace['export_to_csv'] = True
            namespace['method'] = 'GET'
            namespace['action'] = ';export_to_csv'
        # Edit several bugs at once
        namespace['change_several_bugs'] = False
        if query['change_several_bugs']:
            get = resource.get_resource
            namespace['method'] = 'POST'
            namespace['action'] = ';change_several_bugs'
            namespace['change_several_bugs'] = True
            namespace['modules'] = get('modules').get_options()
            namespace['versions'] = get('versions').get_options()
            namespace['priorities'] = get('priorities').get_options()
            namespace['types'] = get('types').get_options()
            namespace['states'] = get('states').get_options()
            users = resource.get_resource('/users')
            namespace['users'] = resource.get_members_namespace('')

        return namespace



class SearchForm(BaseSearchForm, View):

    access = 'is_allowed_to_view'
    title = MSG(u'Search')
    icon = 'button_search.png'

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


#   def GET(self, resource, context):
#       context.query = self.get_query(context)
#       keys = context.get_form_keys()

#       # Proxy (like we do in forms)
#       if ';search' in keys:
#           return self.search(resource, context)

#       # Default view
#       namespace = self.get_namespace(resource, context)
#       handler = resource.get_resource(self.template)
#       return stl(handler, namespace)


    #######################################################################
    # The Search Form
    def get_search_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Build the namespace
        namespace = {}

        # Search Form
        query = context.query
        search_name = query['search_name']
        if search_name:
            search = resource.get_resource(search_name)
            get_value = search.handler.get_value
            get_values = search.get_values
            namespace['search_name'] = search_name
            namespace['search_title'] = search.get_property('title')
        else:
            get_value = query.get
            get_values = query.get
            namespace['search_name'] = None
            namespace['search_title'] = query['search_title']

        namespace['text'] = get_value('text')
        namespace['mtime'] = get_value('mtime')
        module = get_values('module')
        type = get_values('type')
        version = get_values('version')
        priority = get_values('priority')
        assign = get_values('assigned_to')
        state = get_values('state')

        get = resource.get_resource
        namespace['modules'] = get('modules').get_options(module)
        namespace['types'] = get('types').get_options(type)
        namespace['versions'] = get('versions').get_options(version)
        namespace['priorities'] = get('priorities').get_options(priority)
        namespace['states'] = get('states').get_options(state)
        namespace['users'] = resource.get_members_namespace(assign, True)

        # is_admin
        ac = resource.get_access_control()
        namespace['is_admin'] = ac.is_admin(context.user, resource)
        pathto_website = resource.get_pathto(resource.get_site_root())
        namespace['manage_assigned'] = '%s/;permissions' % pathto_website

        return namespace


    def get_namespace(self, resource, context):
        namespace = BaseSearchForm.get_namespace(self, resource, context)
        namespace['batch'] = None
        namespace['table'] = None
        return namespace


##    def action_search(self, resource, context, form):
##       query = context.query
##       search_name = query['search_name']
##       search_title = query['search_title'].strip()
##
##       stored_search = stored_search_title = None
##       if not search_title:
##           context.uri.query['search_name'] = search_name = None
##       if search_name:
##           # Edit an Stored Search
##           try:
##               stored_search = resource.get_resource(search_name)
##               stored_search_title = stored_search.get_property('title')
##           except LookupError:
##               pass
##
##       if search_title and search_title != stored_search_title:
##           # New Stored Search
##           search_name = resource.get_new_id('s')
##           stored_search = StoredSearch.make_object(StoredSearch, resource,
##                                                    search_name)
##
##       view = context.get_form_value('search_view', default=';view')
##       if stored_search is None:
##           # Just Search
##           return context.uri.resolve(view).replace(**context.uri.query)
##
##       # Edit / Title
##       context.commit = True
##       stored_search.set_property('title', search_title, 'en')
##       # Edit / Search Values
##       text = query['text'].strip().lower()
##       stored_search.handler.set_value('text', Unicode.encode(text))
##
##       mtime = query.get('mtime') or 0
##       stored_search.handler.set_value('mtime', mtime)
##
##       criterias = [
##           ('module', Integer), ('version', Integer), ('type', Integer),
##           ('priority', Integer), ('assigned_to', String),
##           ('state', Integer)]
##       for name, type in criterias:
##           value = query[name]
##           stored_search.set_values(name, value, type=type)
##        view = '%s?search_name=%s' % (view, search_name)
##        return context.uri.resolve(view)



class StoredSearchesForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Stored Searches')
    template = '/ui/tracker/stored_searches.xml'
    schema = {
        'ids': String(multiple=True, mandatory=True),
    }


    def get_namespace(self, resource, context):
        stored_searches = [
            {'name': x.name, 'title': x.get_title()}
            for x in resource.search_objects(object_class=StoredSearch) ]
        stored_searches.sort(key=itemgetter('title'))

        return {'stored_searches': stored_searches}


    def action(self, resource, context, form):
        # FIXME This is a simplified version of 'BrowseContent.remove'
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Remove objects
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
            objects = ', '.join(removed)
            context.message = MSG_OBJECTS_REMOVED.gettext(objects=objects)
        else:
            context.message = MSG_NONE_REMOVED



class GoToIssue(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        issue_name = context.get_form_value('issue_name')
        if not issue_name:
            return context.come_back(MSG_NAME_MISSING)

        if not resource.has_resource(issue_name):
            return context.come_back(MSG(u'Issue not found.'))

        issue = resource.get_resource(issue_name)
        if not isinstance(issue, Issue):
            return context.come_back(MSG(u'Issue not found.'))

        return context.uri.resolve2('../%s/;edit' % issue_name)



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
            message = MSG(u"No data to export.")
            return context.come_back(message)

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


class TrackerChangeSeveralBugs(BaseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Change Several Issues')
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
            message = MSG(u"No data to export.")
            return context.come_back(message)

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
            context.server.change_object(issue)

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
        return context.come_back(MSG_CHANGES_SAVED, goto=goto, keep=keep)



###########################################################################
# Model
###########################################################################

class Tracker(Folder):

    class_id = 'tracker'
    class_version = '20080415'
    class_title = MSG(u'Issue Tracker')
    class_description = MSG(u'To manage bugs and tasks')
    class_icon16 = 'images/tracker16.png'
    class_icon48 = 'images/tracker48.png'
    class_views = ['search', 'add_issue', 'stored_searches', 'browse_content',
                   'edit_metadata']

    __fixed_handlers__ = ['modules', 'versions', 'types',
        'priorities', 'states', 'resources']

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
        # Modules and Types Select Tables
        tables = [
            ('modules', [u'Documentation', u'Unit Tests',
                u'Programming Interface', u'Command Line Interface',
                u'Visual Interface']),
            ('types', [u'Bug', u'New Feature', u'Security Issue',
                u'Stability Issue', u'Data Corruption Issue',
                u'Performance Improvement', u'Technology Upgrade'])]
        for table_name, values in tables:
            table = SelectTableTable()
            for title in values:
                table.add_record({'title': title})
            folder.set_handler('%s/%s' % (name, table_name), table)
            metadata = SelectTable.build_metadata()
            folder.set_handler('%s/%s.metadata' % (name, table_name), metadata)
        # Priorities and States Ordered Select Tables
        tables = [
            ('priorities', [u'High', u'Medium', u'Low']),
            ('states', [u'Open', u'Fixed', u'Verified', u'Closed'])]
        for table_name, values in tables:
            table = OrderedSelectTableTable()
            for index, title in enumerate(values):
                table.add_record({'title': title})
            folder.set_handler('%s/%s' % (name, table_name), table)
            metadata = OrderedSelectTable.build_metadata()
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
        metadata = Resources.build_metadata()
        folder.set_handler('%s/resources.metadata' % name, metadata)


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
        users = self.get_resource('/users')
        members = []
        if not_assigned is True:
            members.append({'id': 'nobody', 'title': 'NOT ASSIGNED'})
        for username in self.get_site_root().get_members():
            user = users.get_resource(username)
            members.append({'id': username, 'title': user.get_title()})
        # Select
        if isinstance(value, str):
            value = [value]
        for member in members:
            member['is_selected'] = (member['id'] in value)
        members.sort(key=itemgetter('title'))

        return members


    def get_search_results(self, context, form=None, start=None, end=None):
        """Method that return a list of issues that correspond to the search
        """
        users = self.get_resource('/users')
        # Choose stored Search or personalized search
        search_name = form and form['search_name']
        if search_name:
            try:
                search = self.get_resource(search_name)
            except LookupError:
                goto = ';search'
                msg = u'Unknown stored search "${sname}".'
                return context.come_back(msg, goto=goto, sname=search_name)
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
            query2 = [PhraseQuery('title', text), PhraseQuery('text', text)]
            query = AndQuery(query, OrQuery(*query2))
        for name, data in (('module', modules), ('version', versions),
                           ('type', types), ('priority', priorities),
                           ('state', states)):
            if data != []:
                query2 = []
                for value in data:
                    query2.append(EqQuery(name, value))
                if query2:
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
        return results


    def get_export_to_text(self, context):
        """Generate a text with selected records of selected issues
        """
        # Get selected columns
        selected_columns = context.get_form_values('column_selection')
        if not selected_columns:
            selected_columns = ['title']
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
            # If selected_issues is empty, select all
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


    #######################################################################
    # User Interface
    #######################################################################
    context_menus = [GoToIssueMenu(), StoredSearchesMenu()]

    # Views
    search = SearchForm()
    view = View()
    add_issue = AddIssueForm()
    stored_searches = StoredSearchesForm()
    go_to_issue = GoToIssue()
    export_to_csv = TrackerExportToCSV()
    change_several_bugs = TrackerChangeSeveralBugs()


    #######################################################################
    # Update
    #######################################################################
    def update_20080407(self):
        """Add resources to tracker.
        """
        metadata = Resources.build_metadata()
        self.handler.set_handler('resources.metadata', metadata)


    def update_20080415(self):
        for name in ('priorities', 'states'):
            if not self.has_resource(name):
                continue
            handler = self.get_resource(name)
            handler.metadata.set_changed()
            handler.metadata.format = OrderedSelectTable.class_id
            for index, record in enumerate(handler.handler.get_records()):
                handler.handler.update_record(record.id, rank=str(index))



###########################################################################
# Stored Searches
###########################################################################
class ConfigFile(BaseConfigFile):

    schema = {
        'search_name': Unicode(),
        'mtime': Integer(default=0),
        'module': Integer(multiple=True, default=()),
        'version': Integer(multiple=True, default=()),
        'type': Integer(multiple=True, default=()),
        'priority': Integer(multiple=True, default=()),
        'assigned_to': String(multiple=True, default=()),
        'state': Integer(multiple=True, default=()),
        }


class StoredSearch(Text):

    class_id = 'stored_search'
    class_version = '20071215'
    class_title = MSG(u'Stored Search')
    class_handler = ConfigFile


    def get_values(self, name, type=None):
        return self.handler.get_value(name)


    def set_values(self, name, value, type=String):
        value = [ type.encode(x) for x in value ]
        value = ' '.join(value)
        self.handler.set_value(name, value)



###########################################################################
# Register
###########################################################################
register_object_class(Tracker)
register_object_class(StoredSearch)
