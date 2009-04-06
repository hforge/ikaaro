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
from datetime import datetime

# Import from itools
from itools.csv import CSVFile, Property
from itools.datatypes import Boolean, Integer, String, Unicode, Enumerate
from itools.gettext import MSG
from itools.i18n import format_datetime
from itools.handlers import merge_dicts
from itools.uri import encode_query, Reference
from itools.web import BaseView, BaseForm, STLForm
from itools.web import INFO, ERROR
from itools.web.views import process_form

# Import from ikaaro
from ikaaro.buttons import Button
from ikaaro.forms import HiddenWidget, TextWidget
from ikaaro import messages
from ikaaro.resource_views import DBResource_NewInstance
from ikaaro.views import BrowseForm, SearchForm as BaseSearchForm, ContextMenu

# Import from ikaaro.tracker
from issue import Issue
from datatypes import get_issue_fields, TrackerList, ProductInfoList
from datatypes import UsersList
from stored import StoredSearchFile, StoredSearch


columns = [
    ('id', MSG(u'Id')),
    ('title', MSG(u'Title')),
    ('product', MSG(u'Product')),
    ('module', MSG(u'Module')),
    ('version', MSG(u'Version')),
    ('type', MSG(u'Type')),
    ('state', MSG(u'State')),
    ('priority', MSG(u'Priority')),
    ('assigned_to', MSG(u'Assigned To')),
    ('mtime', MSG(u'Modified'))]



###########################################################################
# Menus
###########################################################################
class GoToIssueMenu(ContextMenu):

    title = MSG(u'Go To Issue')
    template = '/ui/tracker/menu_goto.xml'

    def get_namespace(self, resource, context):
        path_to_tracker = '..' if isinstance(resource, Issue) else '.'
        return {
            'path_to_tracker': path_to_tracker,
            'title': self.title}



class StoreSearchMenu(ContextMenu):
    """Form to store a search.
    """

    title = MSG(u'Remember this search')
    template = '/ui/tracker/menu_remember.xml'
    query_schema = merge_dicts(StoredSearchFile.schema,
                               search_name=String,
                               search_title=Unicode)

    def get_namespace(self, resource, context):
        # This search exists ?
        search_name = context.get_query_value('search_name')
        search = None
        if search_name:
            try:
                search = resource.get_resource(search_name)
            except LookupError:
                pass

        # Set the get function and the title
        if search:
            get = search.get_values
            search_title = search.get_title()
        else:
            # Warning, a menu is not the default view!
            query = process_form(context.get_query_value, self.query_schema)
            get = query.get
            search_title = None

        # Fill the fields
        fields = []
        for name, type in StoredSearchFile.schema.iteritems():
            value = get(name)
            if isinstance(value, list):
                for x in value:
                    fields.append({'name': name, 'value': type.encode(x)})
            elif value is not None:
                fields.append({'name': name, 'value': type.encode(value)})

        # Ok
        return {'title': self.title,
                'search_title': search_title,
                'search_name': search_name,
                'search_fields': fields }



class StoredSearchesMenu(ContextMenu):
    """Provides links to every stored search.
    """

    title = MSG(u'Stored Searches')

    def get_items(self, resource, context):
        language = resource.get_content_language(context)
        root = context.root

        # If called from a child
        if isinstance(resource, Issue):
            resource = resource.parent

        # Namespace
        search_name = context.get_query_value('search_name')
        base = '%s/;view' % context.get_link(resource)
        items = []
        for item in resource.search_resources(cls=StoredSearch):
            # Make the title
            get_value = item.handler.get_value
            query = resource.get_search_query(get_value)
            issues_nb = len(root.search(query))
            kw = {'search_title': item.get_property('title'),
                  'issues_nb': issues_nb}
            title = MSG(u'${search_title} (${issues_nb})')
            title = title.gettext(language=language, **kw)

            # Namespace
            items.append({'title': title,
                          'href': '%s?search_name=%s' % (base, item.name),
                          'class': 'nav_active' if (item.name == search_name)
                                                else None})
        items.sort(lambda x, y: cmp(x['title'], y['title']))

        return items



class TrackerViewMenu(ContextMenu):

    title = MSG(u'Advanced')

    def get_items(self, resource, context):
        # Keep the query parameters
        schema = context.view.get_query_schema()
        params = encode_query(context.query, schema)
        items = [
            {'title': MSG(u'Edit this search'),
             'href': ';search?%s' % params},
            {'title': MSG(u'Change Several Issues'),
             'href': ';change_several_bugs?%s' % params},
            {'title': MSG(u'Export to Text'),
             'href': ';export_to_text?%s' % params},
            {'title': MSG(u'Export to CSV'),
             'href': ';export_to_csv_form?%s' % params},
            {'title': MSG(u'Resources'),
             'href': 'calendar/;monthly_view?%s' % params}]
        return items



###########################################################################
# Views
###########################################################################
class Tracker_NewInstance(DBResource_NewInstance):

    schema = merge_dicts(
        DBResource_NewInstance.schema,
        product=Unicode(mandatory=True))

    widgets = DBResource_NewInstance.widgets + \
        [TextWidget('product', title=MSG(u'Give the title of one Product'))]


    def action(self, resource, context, form):
        ok = DBResource_NewInstance.action(self, resource, context, form)
        if ok is None:
            return

        # Add the initial product
        name = form['name']
        product = form['product']
        table = resource.get_resource('%s/product' % name).get_handler()
        product = Property(product, language='en')
        table.add_record({'title': product})

        # Ok
        return ok



class Tracker_AddIssue(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Add')
    icon = 'new.png'
    template = '/ui/tracker/add_issue.xml'


    def get_schema(self, resource, context):
        return get_issue_fields(resource)


    def get_namespace(self, resource, context):
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

        namespace =  self.build_namespace(resource, context)
        namespace['list_products'] = resource.get_list_products_namespace()

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



class Tracker_View(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'

    schema = {
        'ids': String(multiple=True, mandatory=True)}

    tracker_schema = {
        # Do not batch
        'batch_size': Integer(default=0),
        # search_fields
        'search_name': Unicode(),
        'mtime': Integer(default=0),
        'product': Integer(multiple=True),
        'module': Integer(multiple=True),
        'version': Integer(multiple=True),
        'type': Integer(multiple=True),
        'state': Integer(multiple=True),
        'priority': Integer(multiple=True),
        'assigned_to': String(multiple=True),
        # Specific fields
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        # BrowseForm fields
        'sort_by': String,
        'reverse': Boolean(default=None),
    }

    context_menus = [StoreSearchMenu(), TrackerViewMenu()]


    def get_query_schema(self):
        return merge_dicts(BrowseForm.get_query_schema(self),
                           self.tracker_schema)


    def GET(self, resource, context):
        # Check stored search
        search_name = context.query['search_name']
        if search_name:
            try:
                search = resource.get_resource(search_name)
            except LookupError:
                msg = MSG(u'Unknown stored search "${sname}".')
                goto = ';search'
                return context.come_back(msg, goto=goto, sname=search_name)
        # Ok
        return BrowseForm.GET(self, resource, context)


    def get_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Default table namespace
        namespace = BrowseForm.get_namespace(self, resource, context)

        # Number of results
        query = context.query
        search_name = query['search_name']
        if search_name:
            search = resource.get_resource(search_name)

        # Keep the search_parameters, clean different actions
        schema = self.get_query_schema()
        namespace['search_parameters'] = encode_query(query, schema)

        return namespace


    def get_items(self, resource, context):
        return resource.get_search_results(context)


    def sort_and_batch(self, resource, context, results):
        query = context.query
        # Stored search, or default
        search_name = query['search_name']
        if search_name:
            search = resource.get_resource(search_name).handler
            sort_by = search.get_value('sort_by')
            reverse = search.get_value('reverse')
        else:
            sort_by = 'title'
            reverse = False
        # Query takes precedence
        if query['sort_by'] is not None:
            sort_by = query['sort_by']
        if query['reverse'] is not None:
            reverse = query['reverse']
        return results.get_documents(sort_by=sort_by, reverse=reverse)


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            selected_issues = context.get_form_values('ids') or []
            return item.name, item.name in selected_issues
        if column == 'id':
            id = item.name
            return id, '%s/;edit' % id

        value = getattr(item, column)
        if value is None:
            return None
        if column == 'title':
            return value, '%s/;edit' % item.name
        # Assigned to
        if column == 'assigned_to':
            users = resource.get_resource('/users')
            try:
                user = users.get_resource(value)
            except LookupError:
                return None
            return user.get_title()
        # Mtime
        if column == 'mtime':
            mtime = datetime.strptime(value, '%Y%m%d%H%M%S')
            return format_datetime(mtime)

        # Tables
        table = resource.get_resource(column).handler
        table_record = table.get_record(value)
        if table_record is None:
            return None
        return table.get_record_value(table_record, 'title')


    table_actions = []


    def get_table_columns(self, resource, context):
        table_columns = columns[:]
        table_columns.insert(0, ('checkbox', None))
        return table_columns



class Tracker_Search(BaseSearchForm, Tracker_View):

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
        'product': Integer(multiple=True),
        'module': Integer(multiple=True),
        'version': Integer(multiple=True),
        'type': Integer(multiple=True),
        'state': Integer(multiple=True),
        'priority': Integer(multiple=True),
        'assigned_to': String(multiple=True)
        }

    context_menus = []

    def get_search_namespace(self, resource, context):
        # Set Style & JS
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

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
        product = get_values('product')
        module = get_values('module')
        version = get_values('version')
        type = get_values('type')
        state = get_values('state')
        priority = get_values('priority')
        assigned_to = get_values('assigned_to')

        # is_admin
        ac = resource.get_access_control()
        pathto_website = resource.get_pathto(resource.get_site_root())

        return  {
           'search_name': search_name,
           'search_title': search_title,
           'text': get_value('text'),
           'mtime': get_value('mtime'),
           'is_admin': ac.is_admin(context.user, resource),
           'manage_assigned': '%s/;browse_users' % pathto_website,
           'products': TrackerList(element='product',
                                   tracker=resource).get_namespace(product),
           'modules': ProductInfoList(element='module',
                                      tracker=resource).get_namespace(module),
           'versions': ProductInfoList(element='version',
                                     tracker=resource).get_namespace(version),
           'types': TrackerList(element='type',
                                tracker=resource).get_namespace(type),
           'states': TrackerList(element='state',
                                 tracker=resource).get_namespace(state),
           'priorities': TrackerList(element='priority',
                                 tracker=resource).get_namespace(priority),
           'assigned_to': UsersList(tracker=resource).get_namespace(
                                                         assigned_to),
           'list_products': resource.get_list_products_namespace()}


    def get_namespace(self, resource, context):
        namespace = BaseSearchForm.get_namespace(self, resource, context)
        namespace['batch'] = None
        namespace['table'] = None
        return namespace



class Tracker_RememberSearch(BaseForm):

    access = 'is_allowed_to_edit'
    schema = merge_dicts(StoredSearchFile.schema,
                         search_name=String,
                         search_title=Unicode(mandatory=True))


    def GET(self, resource, context):
        # Required for when the form fails the automatic checks
        return context.come_back(message=context.message)


    def action(self, resource, context, form):
        search_name = form.get('search_name')
        title = form['search_title']

        # Already a search name ?

        # No
        if search_name is None:
            # Search for a search with the same title
            if isinstance(resource, Issue):
                resource = resource.parent
            searches = resource.search_resources(cls=StoredSearch)
            for search in searches:
                # Found !
                if title == search.get_property('title'):
                    search_name = search.name
                    message = MSG(u'The search has been modified.')
                    break
            else:
                # Not found => so we make a new search resource
                search_name = resource.get_new_id('s')
                search = StoredSearch.make_resource(StoredSearch, resource,
                                                    search_name)
                message = MSG(u'The search has been stored.')
        # Yes
        else:
            search = resource.get_resource(search_name)
            message = MSG(u'The search title has been changed.')

        # Reset the search
        search.handler.load_state_from_string('')

        # Set title
        search.set_property('title', title)

        # Save the value
        for name, type in StoredSearchFile.schema.iteritems():
            value = form[name]
            if value:
                search.set_values(name, value, type)

        # Go
        return context.come_back(message, goto=';view?search_name=%s' %
                                          search_name)



class Tracker_ForgetSearch(BaseForm):

    access = 'is_allowed_to_edit'
    schema = {
        'search_name': String(mandatory=True)}


    def action(self, resource, context, form):
        name = form['search_name']
        resource.del_resource(name)
        # Ok
        message = MSG(u'The search has been removed.')
        return context.come_back(message, goto=';search')



class Tracker_GoToIssue(BaseView):

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



class Tracker_ExportToCSVForm(Tracker_View):

    template = '/ui/tracker/export_to_csv.xml'
    external_form = True

    def get_query_schema(self):
        schema = Tracker_View.get_query_schema(self)
        schema['ids'] = String(multiple=True, default=[])
        return schema


    def get_namespace(self, resource, context):
        namespace = Tracker_View.get_namespace(self, resource, context)
        query = context.query

        # Insert query parameters as hidden input fields
        parameters = []
        schema = Tracker_View.get_query_schema(self)
        for name in schema:
            if name in namespace:
                continue
            value = query[name]
            datatype = schema[name]
            widget = HiddenWidget(name)
            if datatype.multiple is True:
                for value in value:
                    parameters.append(widget.to_html(datatype, value))
            elif value:
                parameters.append(widget.to_html(datatype, value))
        namespace['search_parameters'] = parameters

        return namespace



class Tracker_ExportToCSV(BaseView):

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
            issue = get_issue_informations(resource, issue)
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



class Tracker_ExportToText(Tracker_ExportToCSVForm):

    template = '/ui/tracker/export_to_text.xml'

    def get_query_schema(self):
        schema = Tracker_ExportToCSVForm.get_query_schema(self)
        schema['column_selection'] = String(multiple=True, default=['title'])
        return schema


    def get_namespace(self, resource, context):
        namespace = Tracker_ExportToCSVForm.get_namespace(self, resource,
                                                          context)
        query = context.query

        # Column Selector
        selection = query['column_selection']
        export_columns = columns[2:] + [columns[1]]
        namespace['columns'] = [
            {'name': name, 'title': title, 'checked': name in selection}
            for name, title in export_columns ]

        # Text
        items = self.get_items(resource, context)
        items = self.sort_and_batch(resource, context, items)
        selected_items = query['ids']
        if selected_items:
            items = [ x for x in items if x.name in selected_items ]
        items = [ get_issue_informations(resource, x) for x in items ]
        # Create the text
        lines = []
        for item in items:
            name = item['name']
            line = [u'#%s' % name]
            for x in selection:
                value = item[x]
                if type(value) is unicode:
                    pass
                elif type(value) is str:
                    value = unicode(value, 'utf-8')
                else:
                    value = unicode(value)
                line.append(value)
            line = u'\t'.join(line)
            lines.append(line)
        namespace['text'] = u'\n'.join(lines)

        # Ok
        return namespace



class Tracker_ChangeSeveralBugs(Tracker_View):

    access = 'is_allowed_to_view'
    title = MSG(u'Change Several Issues')
    template = '/ui/tracker/change_bugs.xml'
    schema = {
        'comment': Unicode,
        'ids': String(multiple=True),
        'change_product': Integer,
        'change_module': Integer,
        'change_version': Integer,
        'change_type': Integer,
        'change_priority': Integer,
        'change_assigned_to': String,
        'change_state': Integer,
    }

    external_form = True

    table_actions = [
        Button(name='change_several_bugs', title=MSG(u'Edit issues'))]


    def get_namespace(self, resource, context):
        context.scripts.append('/ui/tracker/tracker.js')
        namespace = Tracker_View.get_namespace(self, resource, context)
        # Edit several bugs at once
        get_resource = resource.get_resource
        namespace['products'] = get_resource('product').get_options()
        namespace['modules'] = get_resource('module').get_options()
        namespace['versions'] = get_resource('version').get_options()
        namespace['priorities'] = get_resource('priority').get_options()
        namespace['types'] = get_resource('type').get_options()
        namespace['states'] = get_resource('state').get_options()
        namespace['users'] = resource.get_members_namespace('')
        namespace['list_products'] = resource.get_list_products_namespace()

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
        names = ['product', 'module', 'version', 'type', 'priority', 'state']
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
                'product': issue.get_value('product'),
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
            for name in names:
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

        context.message = messages.MSG_CHANGES_SAVED



def get_issue_informations(resource, item):
    """Construct a dict with issue informations.  This dict is used to
    construct a line for a table.
    """
    # Build the namespace
    infos = {
        'name': item.name,
        'id': item.id,
        'title': item.title,
    }

    # Select Tables
    get_resource = resource.get_resource
    tables = ['product', 'module', 'version', 'type', 'state', 'priority']
    for name in tables:
        infos[name] = None
        value = getattr(item, name)
        if value is None:
            continue
        table = get_resource(name).handler
        table_record = table.get_record(value)
        if table_record is None:
            continue
        infos[name] = table.get_record_value(table_record, 'title')

    # Assigned-To
    assigned_to = getattr(item, 'assigned_to')
    infos['assigned_to'] = ''
    if assigned_to:
        users = resource.get_resource('/users')
        if users.has_resource(assigned_to):
            user = users.get_resource(assigned_to)
            infos['assigned_to'] = user.get_title()

    # Modification Time
    mtime_sort = item.mtime
    mtime = datetime.strptime(mtime_sort, '%Y%m%d%H%M%S')
    infos['mtime'] = format_datetime(mtime)
    infos['mtime_sort'] = mtime_sort

    return infos


