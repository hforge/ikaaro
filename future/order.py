# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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

# Import from itools
from itools.datatypes import String, Tokens
from itools.gettext import MSG
from itools.handlers import merge_dicts
from itools.web import INFO
from itools.xapian import AndQuery, PhraseQuery, StartQuery
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.buttons import Button
from ikaaro.folder_views import Folder_BrowseContent
from ikaaro.forms import PathSelectorWidget
from ikaaro.registry import register_resource_class
from ikaaro.resource_views import Breadcrumb, DBResource_AddLink
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View
from ikaaro.views import BrowseForm, CompositeForm
from ikaaro.workflow import WorkflowAware


class AddButton(Button):

    access = 'is_allowed_to_edit'
    name = 'add'
    title = MSG(u'Add to ordered list')



###########################################################################
# ResourcesOrderedTable
###########################################################################

class ResourcesOrderedTable_Ordered(OrderedTable_View):

    title = MSG('Ordered items')

    def get_table_columns(self, resource, context):
        columns = OrderedTable_View.get_table_columns(self, resource, context)
        # Remove column with id and replace it by title,
        # and add a column for the workflow state
        columns[1] = ('title', MSG(u'Title'))
        columns.append(('workflow_state', MSG(u'State')))
        return columns


    def get_item_value(self, resource, context, item, column):
        try:
            item_resource = resource.get_resource_by_name(item.name, context)
        except LookupError:
            item_resource = None

        if column == 'title':
            if item_resource:
                title = item_resource.get_title()
                return title, context.get_link(item_resource)
            # Miss
            return item.name
        elif column == 'workflow_state':
            # The workflow state
            if item_resource is None:
                # Miss
                label = MSG(u'Broken').gettext().encode('utf-8')
                state = '<strong class="broken">%s</strong>' % label
                return XMLParser(state)
            if not isinstance(item_resource, WorkflowAware):
                return None
            statename = item_resource.get_statename()
            state = item_resource.get_state()
            msg = state['title'].gettext().encode('utf-8')
            path = context.get_link(item_resource)
            # TODO Include the template in the base table
            state = ('<a href="%s/;edit_state" class="workflow">'
                     '<strong class="wf_%s">%s</strong>'
                     '</a>') % (path, statename, msg)
            return XMLParser(state)
        return OrderedTable_View.get_item_value(self, resource, context, item,
                                                column)


class ResourcesOrderedTable_Unordered(Folder_BrowseContent):

    access = 'is_allowed_to_edit'
    title = MSG('Unordered items')

    table_columns = [
        ('checkbox', None),
        ('title', MSG(u'Title')),
        ('path', MSG(u'Path')),
        ('workflow_state', MSG(u'State'))]

    table_actions = [AddButton]

    # Reset unrequired stuff
    context_menus = []
    search_template = None
    search_schema = {}
    def get_search_namespace(self, resource, context):
        return {}
    def get_query_schema(self):
        return {}


    def get_items(self, resource, context):
        exclude = [resource.name] + list(resource.get_ordered_names())
        orderable_classes = resource.get_orderable_classes() or ()
        path = resource.get_root_order_path(context)

        query = [StartQuery('abspath', str(path))]
        for cl in orderable_classes:
            query.append(PhraseQuery('format', cl.class_id))
        query = AndQuery(*query)
        root = context.root
        results = root.search(query).get_documents()
        items = []
        for item in results:
            if item.name not in exclude:
                item = root.get_resource(item.abspath)
                items.append(item)
        return items


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.name, False
        if column == 'title':
            return item.get_title(), context.get_link(item)
        if column == 'path':
            return item.name
        if column == 'workflow_state':
            # The workflow state
            if not isinstance(item, WorkflowAware):
                return None
            statename = item.get_statename()
            state = item.get_state()
            msg = state['title'].gettext().encode('utf-8')
            path = context.get_link(item)
            # TODO Include the template in the base table
            state = ('<a href="%s/;edit_state" class="workflow">'
                     '<strong class="wf_%s">%s</strong>'
                     '</a>') % (path, statename, msg)
            return XMLParser(state)


    def sort_and_batch(self, resource, context, items):
        return items


    def action_add(self, resource, context, form):
        handler = resource.handler

        order = resource.get_property('order') or []
        if not isinstance(order, list):
            order = list(order)

        index = handler.get_n_records()
        for name in form['ids']:
            handler.add_record({'name': name})
            order.append(str(index))
            index += 1

        resource.set_property('order', order)
        context.message = INFO(u'Resources added to ordered list.')



class ResourcesOrderedTable_View(CompositeForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'View')
    template = '/ui/future/order_view.xml'

    subviews = [ResourcesOrderedTable_Ordered(),
                ResourcesOrderedTable_Unordered()]


    def get_namespace(self, resource, context):
        views = []
        for view in self.subviews:
            views.append({'title': view.title,
                          'view': view.GET(resource, context)})
        return {'views': views}


###########################################################################
# ChildrenOrderedTable
###########################################################################

class ChildrenOrderedTable_Ordered(ResourcesOrderedTable_Ordered):
    pass



class ChildrenOrderedTable_Unordered(ResourcesOrderedTable_Unordered):

    def get_items(self, resource, context):
        exclude = [resource.name] + list(resource.get_ordered_names())
        orderable_classes = resource.get_orderable_classes() or ()
        items = []
        for item in resource.parent.search_resources(cls=orderable_classes):
            if item.name not in exclude:
                items.append(item)
        return items



class ChildrenOrderedTable_View(ResourcesOrderedTable_View):

    subviews = [ChildrenOrderedTable_Ordered(),
                ChildrenOrderedTable_Unordered()]



class ChildrenOrderedTable_AddLink(DBResource_AddLink):

    access = 'is_allowed_to_edit'
    template = '/ui/future/order_addlink.xml'

    def get_namespace(self, resource, context):
        namespace = DBResource_AddLink.get_namespace(self, resource, context)
        exclude = [resource.name] + list(resource.get_ordered_names())
        orderable_classes = resource.get_orderable_classes() or ()

        # Construct namespace
        start = resource.parent
        bc = Breadcrumb(root=start, start=start, icon_size=48)
        items = []
        for item in bc.items:
            item_type = item['type']
            if item['name'] in exclude:
                continue
            if not issubclass(item_type, orderable_classes):
                continue
            path = str(item['path'])
            if path.startswith('../'):
                item['path'] = path[3:]
            items.append(item)
        bc.items = items
        namespace['bc'] = bc
        namespace['target_id'] = context.get_form_value('target_id')

        return namespace


###########################################################################
# Resources
###########################################################################

class ResourcesOrderedTableFile(OrderedTableFile):

    record_schema = {'name': String(mandatory=True, unique=True, index='keyword')}



class ChildrenOrderedTableFile(ResourcesOrderedTableFile):
    # FIXME 0.60 -> to remove
    record_schema = {'name': String}



class ResourcesOrderedTable(OrderedTable):

    class_id = 'resources-ordered-table'
    class_title = MSG(u'Resources Ordered Table')
    class_handler = ResourcesOrderedTableFile

    orderable_classes = None
    form = [PathSelectorWidget('name', title=MSG(u'Path'))]


    @classmethod
    def get_metadata_schema(cls):
        return merge_dicts(OrderedTable.get_metadata_schema(),
                           order=Tokens(default=()))


    def get_orderable_classes(self):
        return self.orderable_classes


    def get_root_order_path(self, context):
        """ Every item will be into this path. """
        return context.root.get_abspath()


    def get_ordered_names(self):
        for record in self.handler.get_records_in_order():
            yield record.name


    def get_resource_by_name(self, name, context):
        root_order_path = self.get_root_order_path(context)
        folder = self.get_resource(root_order_path)
        return folder.get_resource(name)


    def get_links(self):
        base = self.get_abspath()
        handler = self.handler
        links = []

        for record in handler.get_records_in_order():
            # Target resources
            path = handler.get_record_value(record, 'name')
            links.append(str(base.resolve(path)))

        return links



class ChildrenOrderedTable(ResourcesOrderedTable):

    class_id = 'children-ordered-table'
    class_title = MSG(u'Children Ordered Table')
    class_handler = ChildrenOrderedTableFile


    def get_root_order_path(self, context):
        """ Every item will be into this path. """
        return self.parent.get_abspath()


    def get_resource_by_name(self, name, context):
        return self.parent.get_resource(name)

    # Views
    add_link = ChildrenOrderedTable_AddLink()
    ordered = ChildrenOrderedTable_Ordered()
    unordered = ChildrenOrderedTable_Unordered()
    view = ChildrenOrderedTable_View()


register_resource_class(ResourcesOrderedTable)
register_resource_class(ChildrenOrderedTable)
