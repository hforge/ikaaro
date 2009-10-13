# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.csv import UniqueError, Property, is_multilingual
from itools.datatypes import Integer, Enumerate, Tokens
from itools.gettext import MSG
from itools.web import INFO, ERROR, BaseView, FormError
from itools.xapian import PhraseQuery

# Import from ikaaro
from autoform import AutoForm
from buttons import RemoveButton, OrderUpButton, OrderDownButton
from buttons import OrderBottomButton, OrderTopButton
import messages
from resource_views import EditLanguageMenu
from views import SearchForm



class Table_View(SearchForm):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    title = MSG(u'View')
    icon = 'view.png'

    schema = {
        'ids': Integer(multiple=True, mandatory=True),
    }

    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_search_schema(self, resource, context):
        return resource.handler.record_properties


    def get_items(self, resource, context):
        search_query = None

        # Build the search query
        if self.search_template is not None:
            query = context.query
            search_term = query['search_term'].strip()
            if search_term:
                search_field = query['search_field']
                search_query = PhraseQuery(search_field, search_term)

        # Ok
        items = resource.handler.search(search_query)
        return list(items)


    def get_search_fields(self, resource, context):
        search_fields = []
        schema = self.get_search_schema(resource, context)
        for widget in self.get_widgets(resource, context):
            if hasattr(schema[widget.name], 'index'):
                title = getattr(widget, 'title', widget.name)
                search_fields.append((widget.name, title))
        return search_fields


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        if sort_by:
            get_record_value = resource.handler.get_record_value
            items.sort(key=lambda x: get_record_value(x, sort_by),
                       reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        if size > 0:
            return items[start:start+size]
        return items[start:]


    def get_table_columns(self, resource, context):
        columns = [
            ('checkbox', None),
            ('id', MSG(u'id'))]
        # From the schema
        for widget in self.get_widgets(resource, context):
            column = (widget.name, getattr(widget, 'title', widget.name))
            columns.append(column)

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.id, False
        elif column == 'id':
            id = item.id
            link = context.get_link(resource)
            return id, '%s/;edit_record?id=%s' % (link, id)

        # Columns
        handler = resource.handler
        value = handler.get_record_value(item, column)
        datatype = handler.get_record_datatype(column)

        # Multilingual
        if is_multilingual(datatype):
            return value

        # Multiple
        is_multiple = datatype.multiple
        is_tokens = issubclass(datatype, Tokens)

        if is_multiple or is_tokens:
            if is_multiple:
                value.sort()
            value_length = len(value)
            if value_length > 0:
                value = value[0]
            else:
                value = None

        # Enumerate
        is_enumerate = getattr(datatype, 'is_enumerate', False)
        if is_enumerate:
            value = datatype.get_value(value)

        return value


    table_actions = [RemoveButton]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)
        # Reindex the resource
        context.change_resource(resource)
        context.message = INFO(u'Record deleted.')



###########################################################################
# Add/Edit records
###########################################################################
class Table_AddEditRecord(AutoForm):

    access = 'is_allowed_to_edit'
    context_menus = [EditLanguageMenu()]


    def get_schema(self, resource, context):
        return resource.get_schema()


    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_field_title(self, resource, name):
        for widget in resource.get_form():
            if widget.name == name:
                title = getattr(widget, 'title', None)
                if title:
                    return title.gettext()
                return name
        return name


    def action(self, resource, context, form):
        """Code shared by the add & edit actions.  It builds a new record
        from the form.
        """
        schema = self.get_schema(resource, context)
        language = resource.get_content_language(context)

        # Builds a new record from the form.
        record = {}
        for name in schema:
            datatype = schema[name]
            value = form[name]
            if is_multilingual(datatype):
                value = value[0]
                value = Property(value, language=language)
            elif datatype.multiple:
                # textarea -> string
                if not issubclass(datatype, Enumerate):
                    value = [ x.strip() for x in value.splitlines() ]
                    value = [ datatype.decode(x) for x in value if x ]
            record[name] = value

        # Change
        try:
            self.action_add_or_edit(resource, context, record)
        except UniqueError, error:
            title = self.get_field_title(resource, error.name)
            context.message = ERROR(str(error), field=title, value=error.value)
        except ValueError, error:
            message = ERROR(u'Error: {msg}', msg=str(error))
            context.message = message
        else:
            return self.action_on_success(resource, context)



class Table_AddRecord(Table_AddEditRecord):

    title = MSG(u'Add Record')
    icon = 'new.png'
    submit_value = MSG(u'Add')


    def action_add_or_edit(self, resource, context, record):
        resource.handler.add_record(record)
        # Reindex the resource
        context.change_resource(resource)


    def action_on_success(self, resource, context):
        n = len(resource.handler.records) - 1
        goto = ';edit_record?id=%s' % n
        return context.come_back(MSG(u'New record added.'), goto=goto)



class Table_EditRecord(Table_AddEditRecord):

    title = MSG(u'Edit record {id}')
    query_schema = {'id': Integer(mandatory=True)}


    def get_query(self, context):
        query = Table_AddEditRecord.get_query(self, context)
        # Test the id is valid
        id = query['id']
        resource = context.resource
        handler = resource.get_handler()
        record = handler.get_record(id)
        if record is None:
            context.query = query
            raise FormError, MSG(u'The {id} record is missing.', id=id)
        # Ok
        return query


    def get_value(self, resource, context, name, datatype):
        handler = resource.get_handler()
        # Get the record
        id = context.query['id']
        record = handler.get_record(id)
        # Is mulitilingual
        if is_multilingual(datatype):
            language = resource.get_content_language(context)
            return handler.get_record_value(record, name, language=language)

        return handler.get_record_value(record, name)


    def get_title(self, context):
        id = context.query['id']
        return self.title.gettext(id=id)


    def action_add_or_edit(self, resource, context, record):
        id = context.query['id']
        resource.handler.update_record(id, **record)
        # Reindex the resource
        context.change_resource(resource)


    def action_on_success(self, resource, context):
        context.message = messages.MSG_CHANGES_SAVED



##########################################################################
# Ordered Views
##########################################################################
class OrderedTable_View(Table_View):

    def get_items(self, resource, context):
        items = resource.handler.get_records_in_order()
        return list(items)


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        if sort_by == 'order':
            reverse = context.query['reverse']
            ordered_ids = list(resource.handler.get_record_ids_in_order())
            f = lambda x: ordered_ids.index(x.id)
            items.sort(cmp=lambda x,y: cmp(f(x), f(y)), reverse=reverse)

            # Batch
            start = context.query['batch_start']
            size = context.query['batch_size']
            return items[start:start+size]

        return Table_View.sort_and_batch(self, resource, context, items)


    def get_table_columns(self, resource, context):
        columns = Table_View.get_table_columns(self, resource, context)
        columns.append(('order', MSG(u'Order')))

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'order':
            ordered_ids = list(resource.handler.get_record_ids_in_order())
            return ordered_ids.index(item.id) + 1

        return Table_View.get_item_value(self, resource, context, item, column)


    table_actions = [RemoveButton, OrderUpButton, OrderDownButton,
                     OrderTopButton, OrderBottomButton]

    ######################################################################
    # Form Actions
    ######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.del_record(id)

        context.message = INFO(u'Record deleted.')


    def action_order_up(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order up.')
            context.message = message
            return

        resource.handler.order_up(ids)
        context.message = INFO(u'Resources ordered up.')


    def action_order_down(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order down.')
            context.message = message
            return

        resource.handler.order_down(ids)
        context.message = INFO(u'Resources ordered down.')


    def action_order_top(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order on top.')
            context.message = message
            return

        resource.handler.order_top(ids)
        context.message = INFO(u'Resources ordered on top.')


    def action_order_bottom(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order on bottom.')
            context.message = message
            return

        resource.handler.order_bottom(ids)
        context.message = INFO(u'Resources ordered on bottom.')



class Table_ExportCSV(BaseView):

    access = 'is_admin'
    title = MSG(u"Export to CSV")
    # String to join multiple values (or they will raise an error)
    multiple_separator = None
    # CSV columns separator
    csv_separator = ','


    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def GET(self, resource, context):
        handler = resource.handler
        columns = ['id'] + [widget.name for widget in self.get_form()]
        language = resource.get_content_language(context)
        csv = handler.to_csv(columns, separator=self.multiple_separator,
                             language=language)

        # Ok
        context.set_content_type('text/comma-separated-values')
        name = resource.get_name()
        context.set_content_disposition('inline', '%s.csv' % name)
        return csv.to_str(separator=self.csv_separator)

