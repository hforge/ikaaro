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

# Import from ikaaro
from ikaaro.future.menu import PathWidget
from ikaaro.registry import register_resource_class
from ikaaro.resource_views import Breadcrumb, DBResource_AddLink
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View


class ChildrenOrderedTable_View(OrderedTable_View):

    def get_table_columns(self, resource, context):
        columns = OrderedTable_View.get_table_columns(self, resource, context)
        columns.insert(2, ('title', MSG(u'Title')))
        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'title':
            item = resource.parent.get_resource(item.name)
            return item.get_title()
        return OrderedTable_View.get_item_value(self, resource, context, item,
                                                column)


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
    form = [PathWidget('name', title=MSG(u'Path'))]


    def get_orderable_classes(self):
        return self.orderable_classes


    def get_ordered_names(self):
        for record in self.handler.get_records_in_order():
            yield record.name


    # Views
    add_link = ChildrenOrderedTable_AddLink()
    view = ChildrenOrderedTable_View()


register_resource_class(ChildrenOrderedTable)
