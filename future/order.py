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
from itools.datatypes import String
from itools.gettext import MSG
from itools.web import INFO

# Import from ikaaro
from ikaaro.buttons import Button
from ikaaro.folder_views import Folder_BrowseContent
from ikaaro.forms import PathSelectorWidget
from ikaaro.registry import register_resource_class
from ikaaro.resource_views import Breadcrumb, DBResource_AddLink
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View
from ikaaro.views import BrowseForm, CompositeForm


class AddButton(Button):

    access = 'is_allowed_to_edit'
    name = 'add'
    title = MSG(u'Add to ordered list')



class ChildrenOrderedTable_Ordered(OrderedTable_View):

    title = MSG('Ordered items')

    def get_table_columns(self, resource, context):
        columns = OrderedTable_View.get_table_columns(self, resource, context)
        # Remove column with id and replace it by title
        columns[1] = ('title', MSG(u'Title'))
        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'title':
            item = resource.parent.get_resource(item.name)
            return item.get_title(), context.get_link(item)
        return OrderedTable_View.get_item_value(self, resource, context, item,
                                                column)



class ChildrenOrderedTable_Unordered(Folder_BrowseContent):

    access = 'is_allowed_to_edit'
    title = MSG('Unordered items')

    table_columns = [
        ('checkbox', None),
        ('title', MSG(u'Title')),
        ('path', MSG(u'Chemin'))]

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
        items = []
        for item in resource.parent.search_resources(cls=orderable_classes):
            if item.name not in exclude:
                items.append(item)
        return items


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.name, False
        if column == 'title':
            return item.get_title(), context.get_link(item)
        if column == 'path':
            return item.name


    def sort_and_batch(self, resource, context, items):
        return items


    def action_add(self, resource, context, form):
        parent = resource.parent
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



class ChildrenOrderedTable_View(CompositeForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'View')
    template = '/ui/future/order_view.xml'

    subviews = [ChildrenOrderedTable_Ordered(),
                ChildrenOrderedTable_Unordered()]


    def get_namespace(self, resource, context):
        views = []
        for view in self.subviews:
            views.append({'title': view.title,
                          'view': view.GET(resource, context)})
        return {'views': views}



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



class ChildrenOrderedTableFile(OrderedTableFile):

    record_schema = {'name': String}



class ChildrenOrderedTable(OrderedTable):

    class_id = 'children-ordered-table'
    class_title = MSG(u'Children Ordered Table')
    class_handler = ChildrenOrderedTableFile

    orderable_classes = None
    form = [PathSelectorWidget('name', title=MSG(u'Path'))]


    def get_orderable_classes(self):
        return self.orderable_classes


    def get_ordered_names(self):
        for record in self.handler.get_records_in_order():
            yield record.name


    # Views
    add_link = ChildrenOrderedTable_AddLink()
    ordered = ChildrenOrderedTable_Ordered()
    unordered = ChildrenOrderedTable_Unordered()
    view = ChildrenOrderedTable_View()


register_resource_class(ChildrenOrderedTable)
