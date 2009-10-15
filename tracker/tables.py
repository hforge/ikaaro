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
from itools.core import merge_dicts
from itools.datatypes import Boolean, String, Unicode
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.xapian import PhraseQuery, AndQuery

# Import from ikaaro
from ikaaro.autoform import title_widget, CheckboxWidget, SelectWidget
from ikaaro.autoform import ReadOnlyWidget
from ikaaro.table import OrderedTable, OrderedTableFile
from ikaaro.table_views import OrderedTable_View, Table_EditRecord



class ProductsEnumerate(Enumerate):

    def get_options(cls):
        products = cls.products.handler
        return [
            {'name': str(x.id),
             'value': products.get_record_value(x, 'title')}
            for x in products.get_records_in_order() ]


###########################################################################
# Views
###########################################################################
class SelectTable_View(OrderedTable_View):

    access = 'is_allowed_to_view'

    def get_table_columns(self, resource, context):
        cls = OrderedTable_View
        columns = cls.get_table_columns(self, resource, context)
        columns.append(('issues', MSG(u'Issues')))
        if resource.name == 'product':
            # Add specific columns for the product table
            columns.append(('modules', MSG(u'Modules')))
            columns.append(('versions', MSG(u'Versions')))
        return columns


    def get_item_value(self, resource, context, item, column):
        tracker = resource.get_parent()
        # Append a column with the number of issues
        if column == 'issues':
            filter = str(resource.name)

            # Build the search query
            query_terms = tracker.get_issues_query_terms()
            query_terms.append(PhraseQuery(filter, item.id))
            query = AndQuery(*query_terms)

            # Search
            results = context.search(query)
            count = len(results)
            if count == 0:
                return 0, None
            return count, '../;view?%s=%s' % (filter, item.id)
        # Don't show the "edit" link when i am not an admin.
        elif column == 'id':
            ac = resource.get_access_control()
            is_admin =  ac.is_admin(context.user, resource)

            id = item.id
            if is_admin:
                link = context.get_link(resource)
                return id, '%s/;edit_record?id=%s' % (link, id)
            else:
                return id

        # Default
        cls = OrderedTable_View
        value = cls.get_item_value(self, resource, context, item, column)

        # FIXME The field 'product' is reserved to make a reference to the
        # 'products' table.  Currently it is used by the 'versions' and
        # 'modules' tables.
        # The fields 'modules' and 'versions' is reserved to make reference to
        # the 'modules' and 'versions' tables. Currently it is used by the
        # 'product' table
        if column == 'product':
            value = int(value)
            handler = tracker.get_resource('product').handler
            record = handler.get_record(value)
            return handler.get_record_value(record, 'title')
        elif column in ('modules', 'versions'):
            # Strip 's' modules -> module
            associated_table = resource.get_resource('../%s' % column[:-1])
            handler = associated_table.handler
            # Search
            results = handler.search(PhraseQuery('product', str(item.id)))
            count = len(results)
            if count == 0:
                return 0, None
            return count, '%s/;view' % context.get_link(associated_table)

        return value


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        if sort_by != 'issues':
            cls = OrderedTable_View
            return cls.sort_and_batch(self, resource, context, items)

        reverse = context.query['reverse']
        f = lambda x: self.get_item_value(resource, context, x, 'issues')[0]
        items.sort(cmp=lambda x,y: cmp(f(x), f(y)), reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    def action_remove(self, resource, context, form):
        ids = form['ids']
        parent = resource.get_parent()
        # Search all issues
        query_terms = parent.get_issues_query_terms()
        query = AndQuery(*query_terms)
        results = context.search(query)

        # Associated modules and versions
        check_associated = (resource.name == 'product')
        module = parent.get_resource('module')
        version = parent.get_resource('version')
        module_handler = module.handler
        version_handler = version.handler

        # Remove values only if no issues have them
        handler = resource.handler
        filter = str(resource.name)
        removed = []
        for id in ids:
            query = PhraseQuery(filter, id)
            count = len(results.search(query))
            if check_associated:
                product_query = PhraseQuery('product', str(id))
                module_count = len(module_handler.search(product_query))
                version_count = len(version_handler.search(product_query))
                count = count + module_count + version_count
            if count == 0:
                handler.del_record(id)
                removed.append(str(id))

        # Ok
        message = MSG(u'Resources removed: {resources}.')
        message = message.gettext(resources=', '.join(removed)).encode('utf-8')
        context.message = message



class SelectTable_EditRecord(Table_EditRecord):

    def get_widgets(self, resource, context):
        widgets = Table_EditRecord.get_widgets(self, resource, context)
        return [ widget if widget.name != 'product' else
                 ReadOnlyWidget('product', title=MSG(u'Product'))
                 for widget in widgets ]



###########################################################################
# Resources
###########################################################################
class Tracker_TableHandler(OrderedTableFile):

    record_properties = {'title': Unicode(multiple=True)}



class Tracker_TableResource(OrderedTable):

    class_id = 'tracker_select_table'
    class_title = MSG(u'Select Table')
    class_handler = Tracker_TableHandler

    form = [title_widget]


    def get_options(self, value=None, sort=None):
        # Find out the options
        handler = self.handler
        options = []
        for id in handler.get_record_ids_in_order():
            record = handler.get_record(id)
            title = handler.get_record_value(record, 'title')
            options.append({'id': id, 'title': title})

        # Sort
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


    view = SelectTable_View()
    edit_record = SelectTable_EditRecord()



class ModulesHandler(Tracker_TableHandler):

    record_properties = {
        'product': String(mandatory=True, is_indexed=True),
        'title': Unicode(multiple=True, mandatory=True)}



class ModulesResource(Tracker_TableResource):

    class_id = 'tracker_modules'
    class_handler = ModulesHandler

    def get_schema(self):
        products = self.get_resource('../product')
        return merge_dicts(
            ModulesHandler.record_properties,
            product=ProductsEnumerate(products=products, mandatory=True))


    form = [
        SelectWidget('product', title=MSG(u'Product')),
        title_widget]



class VersionsHandler(Tracker_TableHandler):

    record_properties = {
        'product': String(mandatory=True, is_indexed=True),
        'title': Unicode(multiple=True, mandatory=True),
        'released': Boolean}



class VersionsResource(Tracker_TableResource):

    class_id = 'tracker_versions'
    class_handler = VersionsHandler

    def get_schema(self):
        products = self.get_resource('../product')
        return merge_dicts(
            VersionsHandler.record_properties,
            product=ProductsEnumerate(products=products, mandatory=True))


    form = [
        SelectWidget('product', title=MSG(u'Product')),
        title_widget,
        CheckboxWidget('released', title=MSG(u'Released'))]

