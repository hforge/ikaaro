# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.csv import Table as BaseTable
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.datatypes import DynamicEnumerate
from itools.gettext import MSG
from itools.handlers import merge_dics
from itools.xapian import EqQuery, AndQuery
from itools.web import ERROR, INFO

# Import from ikaaro
from ikaaro.forms import title_widget, BooleanCheckBox, SelectWidget
from ikaaro.registry import register_resource_class
from ikaaro.table import Table, OrderedTable, OrderedTableFile
from ikaaro.table_views import TableView



class ProductsEnumerate(DynamicEnumerate):

    def get_options(self):
        products = self.products.handler
        return [
            {'name': str(x.id),
             'value': products.get_record_value(x, 'title')}
            for x in products.get_records() ]


###########################################################################
# Views
###########################################################################
class SelectTableView(TableView):

    def get_table_columns(self, resource, context):
        columns = TableView.get_table_columns(self, resource, context)
        columns.append(('issues', MSG(u'Issues')))
        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'issues':
            # Append a column for the number of issues
            root = context.root
            abspath = resource.parent.get_canonical_path()
            base_query = AndQuery(
                            EqQuery('parent_path', str(abspath)),
                            EqQuery('format', 'issue'))
            search_query = AndQuery(base_query, EqQuery(filter, id))
            results = root.search(search_query)
            count = len(results)
            if count == 0:
                return 0, None
            return count, '../;view?%s=%s' % (filter, id)

        return TableView.get_item_value(self, resource, context, item, column)


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        if sort_by != 'issues':
            return TableView.sort_and_batch(self, resource, context, items)

        reverse = context.query['reverse']
        f = lambda x: self.get_item_value(resource, context, x, 'issues')[0]
        items.sort(cmp=lambda x,y: cmp(f(x), f(y)), reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]



###########################################################################
# Resources
###########################################################################
class TableHandler(BaseTable):

    record_schema = {'title': Unicode}


class TableResource(Table):

    class_id = 'tracker_select_table'
    class_version = '20071216'
    class_title = MSG(u'Select Table')
    class_handler = TableHandler

    form = [title_widget]


    def get_options(self, value=None, sort='title'):
        options = [
            {'id': x.id, 'title': x.title}
            for x in self.handler.get_records() ]

        if sort is not None:
            options.sort(key=lambda x: x.get(sort))
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


    view = SelectTableView()


    def del_record_action(self, context):
        # check input
        ids = context.get_form_values('ids', type=Integer)
        if not ids:
            return context.come_back(ERROR(u'No resource selected.'))

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
            query = AndQuery(base_query, EqQuery(filter, id))
            count = root.search(query).get_n_documents()
            if count == 0:
                self.handler.del_record(id)
                removed.append(str(id))

        message = INFO(u'Resources removed: $resources.')
        return context.come_back(message, resources=', '.join(removed))



class OrderedTableHandler(OrderedTableFile):

    record_schema = {'title': Unicode}


class OrderedTableResource(OrderedTable, TableResource):

    class_id = 'tracker_ordered_select_table'
    class_version = '20080415'
    class_title = MSG(u'Ordered select table')
    class_handler = OrderedTableHandler

    form = [title_widget]


    def get_options(self, value=None, sort=None):
        table = self.handler
        options = []
        for x in table.get_records_in_order():
            ns = {'id': x.id, 'title': x.title}
            options.append(ns)

        if sort is not None:
            options.sort(key=lambda x: x.get(sort))
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



class ModulesHandler(BaseTable):

    record_schema = {
        'product': String(mandatory=True),
        'title': Unicode(mandatory=True)}



class ModulesResource(TableResource):

    class_id = 'tracker_modules'
    class_version = '20081015'
    class_handler = ModulesHandler

    def get_schema(self):
        products = self.parent.get_resource('products')
        return merge_dics(
            ModulesHandler.record_schema,
            product=ProductsEnumerate(products=products, mandatory=True))


    form = [
        SelectWidget('product', title=MSG(u'Product')),
        title_widget]



class VersionsHandler(OrderedTableFile):

    record_schema = {
        'product': String(mandatory=True),
        'title': Unicode(mandatory=True),
        'released': Boolean}



class VersionsResource(OrderedTableResource):

    class_id = 'tracker_versions'
    class_version = '20071216'
    class_handler = VersionsHandler

    def get_schema(self):
        products = self.parent.get_resource('products')
        return merge_dics(
            VersionsHandler.record_schema,
            product=ProductsEnumerate(products=products, mandatory=True))


    form = [
        SelectWidget('product', title=MSG(u'Product')),
        title_widget,
        BooleanCheckBox('released', title=MSG(u'Released'))]



###########################################################################
# Register
###########################################################################
register_resource_class(TableResource)
register_resource_class(OrderedTableResource)
register_resource_class(ModulesResource)
register_resource_class(VersionsResource)
