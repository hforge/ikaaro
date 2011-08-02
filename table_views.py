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
from itools.core import merge_dicts
from itools.csv import UniqueError, Property, is_multilingual
from itools.datatypes import Boolean, Integer, Enumerate, Tokens, Unicode
from itools.gettext import MSG
from itools.web import INFO, ERROR, BaseView, FormError

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from buttons import Button, RemoveButton, AddButton
from order import OrderAware_View
from views import BrowseForm
import messages



class AddRecordButton(AddButton):

    name = 'add_record'
    title = MSG(u'Add record')



class Table_View(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'

    search_schema = {}
    search_widgets = []
    schema = {
        'ids': Integer(multiple=True, mandatory=True)}
    # Add record action does not required any parameters
    action_add_record_schema = {}

    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_items(self, resource, context):
        items = resource.handler.get_records()
        return list(items)


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
            ac = resource.get_access_control()
            view = resource.edit_record
            if not ac.is_access_allowed(context.user, resource, view):
                return id
            link = context.get_link(resource)
            return id, '%s/;edit_record?id=%s' % (link, id)

        # Columns
        value = resource.handler.get_record_value(item, column)
        datatype = resource.get_schema()[column]

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


    table_actions = [AddRecordButton, RemoveButton]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)
        # Reindex the resource
        context.database.change_resource(resource)

        context.message = INFO(u'Record deleted.')


    def action_add_record(self, resource, context, form):
        """Do a redict to add_record view"""

        goto = '%s/;add_record' % context.get_link(resource)
        return context.come_back(None, goto=goto)



###########################################################################
# Add/Edit records
###########################################################################
class Table_AddRecord(AutoAdd):

    title = MSG(u'Add Record')
    icon = 'new.png'
    actions = [Button(access=True, css='button-ok', title=MSG(u'Add'))]


    def _get_resource_schema(self, resource):
        return resource.get_schema()


    def _get_form(self, resource, context):
        return super(AutoAdd, self)._get_form(resource, context)


    def get_value(self, resource, context, name, datatype):
        default = datatype.get_default()
        if not is_multilingual(datatype):
            return default

        value = {}
        for language in resource.get_edit_languages(context):
            value[language] = default
        return value


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
        # Get submit field names
        schema = self.get_schema(resource, context)

        # Builds a new record from the form.
        record = {}
        for name in self.fields:
            datatype = schema[name]
            value = form[name]
            if is_multilingual(datatype):
                value = [ Property(data, language=language)
                          for language, data in value.iteritems() ]
            elif datatype.multiple:
                # textarea -> string
                if not issubclass(datatype, Enumerate):
                    value = [ x.strip() for x in value.splitlines() ]
                    value = [ datatype.decode(x) for x in value if x ]
            record[name] = value

        # Change
        try:
            resource.handler.add_record(record)
            context.database.change_resource(resource) # Reindex
        except UniqueError, error:
            title = self.get_field_title(resource, error.name)
            context.message = ERROR(str(error), field=title, value=error.value)
        except ValueError, error:
            context.message = ERROR(u'Error: {msg}', msg=str(error))
        else:
            return self.action_on_success(resource, context)


    def action_on_success(self, resource, context):
        n = len(resource.handler.records) - 1
        goto = ';edit_record?id=%s' % n
        return context.come_back(MSG(u'New record added.'), goto=goto)



class Table_EditRecord(AutoEdit):

    title = MSG(u'Edit record {id}')


    def _get_resource_schema(self, resource):
        return resource.get_schema()


    def get_query_schema(self):
        schema = super(Table_EditRecord, self).get_query_schema()
        schema['id'] = Integer(mandatory=True)
        return schema


    def _get_query_to_keep(self, resource, context):
        """Keep id"""
        return [{'name': 'id', 'value': context.query['id']}]


    def get_query(self, context):
        query = super(Table_EditRecord, self).get_query(context)
        # Test the id is valid
        id = query['id']
        resource = context.resource
        record = resource.get_record(id)
        if record is None:
            context.query = query
            raise FormError, MSG(u'The {id} record is missing.', id=id)
        # Ok
        return query


    def get_value(self, resource, context, name, datatype):
        if name == 'timestamp':
            proxy = super(Table_EditRecord, self)
            return proxy.get_value(resource, context, name, datatype)

        # Get the record
        id = context.query['id']
        record = resource.get_record(id)
        get_record_value = resource.handler.get_record_value

        # Monolingual
        if not is_multilingual(datatype):
            return get_record_value(record, name)

        # Multilingual
        value = {}
        for language in resource.get_edit_languages(context):
            value[language] = get_record_value(record, name, language=language)
        return value


    def get_title(self, context):
        id = context.query['id']
        return self.title.gettext(id=id)


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
        # Get submit field names
        schema = self._get_schema(resource, context)

        # Builds a new record from the form.
        record = {}
        for name in self.fields:
            datatype = schema[name]
            value = form[name]
            if is_multilingual(datatype):
                value = [ Property(data, language=language)
                          for language, data in value.iteritems() ]
            elif datatype.multiple:
                # textarea -> string
                if not issubclass(datatype, Enumerate):
                    value = [ x.strip() for x in value.splitlines() ]
                    value = [ datatype.decode(x) for x in value if x ]
            record[name] = value

        # Change
        try:
            id = context.query['id']
            resource.handler.update_record(id, **record)
            context.database.change_resource(resource) # Reindex
        except UniqueError, error:
            title = self.get_field_title(resource, error.name)
            context.message = ERROR(str(error), field=title, value=error.value)
        except ValueError, error:
            context.message = ERROR(u'Error: {msg}', msg=str(error))
        else:
            return self.action_on_success(resource, context)


    def action_on_success(self, resource, context):
        context.message = messages.MSG_CHANGES_SAVED


##########################################################################
# Ordered Views
##########################################################################


class OrderedTable_View(Table_View, OrderAware_View):

    query_schema = merge_dicts(Table_View.query_schema,
                               sort_by=Unicode(default='order'),
                               reverse=Boolean(default=False))

    def get_table_actions(self, resource, context):
        proxy = super(OrderedTable_View, self)
        return (proxy.get_table_actions(resource, context) +
                OrderAware_View.get_table_actions(self, resource, context))


    def get_table_columns(self, resource, context):
        proxy = super(OrderedTable_View, self)
        return (proxy.get_table_columns(resource, context) +
                     [('order', MSG(u'Order'))])


    def get_item_value(self, resource, context, item, column):
        if column == 'order':
            ordered_ids = list(resource.get_ordered_values())
            if item.id in ordered_ids:
                return ordered_ids.index(item.id) + 1
            return MSG(u'Not ordered')
        proxy = super(OrderedTable_View, self)
        return proxy.get_item_value(resource, context, item, column)



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
        csv = handler.to_csv(columns, separator=self.multiple_separator)

        # Ok
        context.set_content_type('text/comma-separated-values')
        context.set_content_disposition('inline', '%s.csv' % resource.name)
        return csv.to_str(separator=self.csv_separator)

