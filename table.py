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

# Import from the Standard Library
from copy import deepcopy
from datetime import datetime
from operator import itemgetter

# Import from itools
from itools.csv import Record, UniqueError, Table as TableFile, Property
from itools.datatypes import DataType, is_datatype
from itools.datatypes import Integer, Enumerate, Date, Tokens
from itools.gettext import MSG
from itools.http import Forbidden
from itools.stl import stl
from itools.web import FormError, STLView, get_context, MSG_MISSING_OR_INVALID

# Import from ikaaro
from file import File
from forms import AutoForm, get_default_widget, ReadOnlyWidget
from messages import *
from resource_ import DBResource
from views import BrowseForm


class OrderedTableFile(TableFile):

    def get_datatype(self, name):
        if name == 'order':
            return Tokens()
        return TableFile.get_datatype(self, name)


    #######################################################################
    # Handlers
    #######################################################################
    def new(self):
        # Add the record 0 which stocks the records order
        record = self.record_class(0)
        record.append({
            'ts': Property(datetime.now()),
            'order': Property(())})
        self.records.append(record)


    #######################################################################
    # API / Public
    #######################################################################
    def get_record_ids(self):
        # Override to skip the record '0' (start in '1')
        i = 1
        n = len(self.records)
        while i < n:
            record = self.records[i]
            if record is not None:
                yield i
            i += 1


    def get_record_ids_in_order(self):
        """Return ids sort by order"""
        record_order = self.get_record(0)
        ordered = record_order.get_value('order')
        for id in ordered:
            yield int(id)
        # Unordered
        ordered_set = set(ordered)
        for id in self.get_record_ids():
            if str(id) not in ordered_set:
                yield id


    def get_records_in_order(self):
        for id in self.get_record_ids_in_order():
            yield self.get_record(id)


    #######################################################################
    # Order
    #######################################################################
    def order_up(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        for id in ids:
            index = order.index(id)
            if index > 0:
                order.remove(id)
                order.insert(index - 1, id)
        # Update the order
        order = [ str(x) for x in order ]
        self.update_record(0, order=tuple(order))


    def order_down(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        for id in ids:
            index = order.index(id)
            order.remove(id)
            order.insert(index + 1, id)
        # Update the order
        order = [ str(x) for x in order ]
        self.update_record(0, order=tuple(order))


    def order_top(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        order = ids + [ id for id in order if id not in ids ]
        # Update the order
        order = [ str(x) for x in order ]
        self.update_record(0, order=tuple(order))


    def order_bottom(self, ids):
        order = self.get_record_ids_in_order()
        order = list(order)
        order = [ id for id in order if id not in ids ] + ids
        # Update the order
        order = [ str(x) for x in order ]
        self.update_record(0, order=tuple(order))


###########################################################################
# Views
###########################################################################
class TableView(BrowseForm):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    title = MSG(u'View')
    icon = 'view.png'

    schema = {
        'ids': Integer(multiple=True, mandatory=True),
    }

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
            items.sort(key=itemgetter(sort_by), reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    def get_table_columns(self, resource, context):
        columns = [
            ('checkbox', None),
            ('index', u'id')]
        # From the schema
        for widget in self.get_widgets(resource, context):
            column = (widget.name, getattr(widget, 'title', widget.name))
            columns.append(column)

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.id, False
        elif column == 'index':
            id = item.id
            return id, ';edit_record?id=%s' % id

        # Columns
        handler = resource.handler
        value = handler.get_value(item, column)
        datatype = handler.get_datatype(column)

        multiple = getattr(datatype, 'multiple', False)
        is_tokens = is_datatype(datatype, Tokens)
        if multiple is True or is_tokens:
            if multiple:
                value.sort()
            value_length = len(value)
            if value_length > 0:
                rmultiple = value_length > 1
                value = value[0]
            else:
                rmultiple = False
                value = None

        is_enumerate = getattr(datatype, 'is_enumerate', False)
        if is_enumerate:
            value = datatype.get_value(value)

        if multiple is True or is_tokens:
            return value, rmultiple
        return value


    def get_actions(self, resource, context, items):
        if len(items) == 0:
            return []

        ac = resource.get_access_control()
        if ac.is_allowed_to_edit(context.user, resource):
            message_utf8 = MSG_DELETE_SELECTION.gettext().encode('utf_8')
            return [('remove', u'Remove', 'button_delete',
                     'return confirm("%s");' % message_utf8)]

        return []


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)

        context.message = u'Record deleted.'



class AddRecordForm(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Add Record')
    icon = 'new.png'
    submit_value = MSG(u'Add')
    submit_class = 'button_ok'


    def get_schema(self, resource, context):
        return resource.handler.schema


    def get_widgets(self, resource, context):
        return resource.get_form()


    def action(self, resource, context, form):
        schema = self.get_schema(resource, context)
        handler = resource.handler
#       # check form
#       check_fields = {}
#       for name in schema:
#           datatype = handler.get_datatype(name)
#           if getattr(datatype, 'multiple', False) is True:
#               datatype = Multiple(type=datatype)
#           check_fields[name] = datatype

#       try:
#           form = self.check_form_input(resource, check_fields)
#       except FormError:
#           context.message = MSG_MISSING_OR_INVALID
#           return

        record = {}
        for name in schema:
            datatype = handler.get_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[name]
                else: # textarea -> string
                    values = form[name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[name]
            record[name] = value
        try:
            handler.add_record(record)
            message = u'New record added.'
        except UniqueError, error:
            title = resource.get_field_title(error.name)
            message = str(error) % (title, error.value)
        except ValueError, error:
            title = resource.get_field_title(error.name)
            message = MSG(u'Error: $message')
            message = message.gettext(message=strerror)

        context.message = message


class EditRecordForm(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit record ${id}')
    submit_value = MSG(u'Change')
    submit_class = 'button_ok'
    query_schema = {'id': Integer}


    def get_value(self, resource, context, name, datatype):
        id = context.query['id']
        record = resource.get_handler().get_record(id)
        return resource.handler.get_value(record, name)


    def get_schema(self, resource, context):
        return resource.get_handler().schema


    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_title(self, context):
        id = context.query['id']
        return self.title.gettext(id=id)


    def action(self, resource, context, form):
        id = context.query.get('id')
        if id is None:
            context.message = MSG_MISSING_OR_INVALID
            return

        # check form
        check_fields = {}
        for widget in resource.get_form():
            datatype = resource.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[widget.name] = datatype

        # Get the record
        record = {}
        for widget in resource.get_form():
            datatype = resource.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[widget.name]
                else: # textarea -> string
                    values = form[widget.name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[widget.name]
            record[widget.name] = value

        try:
            resource.handler.update_record(id, **record)
        except UniqueError, error:
            title = resource.get_field_title(error.name)
            context.message = str(error) % (title, error.value)
        except ValueError, error:
            title = resource.get_field_title(error.name)
            message = MSG(u'Error: $message')
            context.message = message.gettext(message=strerror)
        else:
            context.message = MSG_CHANGES_SAVED



class OrderedTableView(TableView):

    def get_items(self, resource, context):
        items = resource.handler.get_records_in_order()
        return list(items)


    def get_actions(self, resource, context, items):
        if len(items) == 0:
            return []

        ac = resource.get_access_control()
        if ac.is_allowed_to_edit(context.user, resource):
            message_utf8 = MSG_DELETE_SELECTION.gettext().encode('utf_8')
            return [('remove', u'Remove', 'button_delete',
                     'return confirm("%s");' % message_utf8),
                    ('order_up', u'Order up', 'button_ok', None),
                    ('order_down', u'Order down', 'button_ok', None),
                    ('order_top', u'Order top', 'button_ok', None),
                    ('order_bottom', u'Order bottom', 'button_ok', None)]

        return []


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)

        context.message = u'Record deleted.'


    def action_order_up(self, resource, context, form):
        ids = form['ids']
        if not ids:
            context.message = MSG(u'Please select the objects to order up.')
            return

        resource.handler.order_up(ids)
        context.message = MSG(u'Objects ordered up.')


    def action_order_down(self, resource, context, form):
        ids = form['ids']
        if not ids:
            context.message = MSG(u'Please select the objects to order down.')
            return

        resource.handler.order_down(ids)
        context.message = MSG(u'Objects ordered down.')


    def action_order_top(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = MSG(u'Please select the objects to order on top.')
            context.message = message
            return

        resource.handler.order_top(ids)
        context.message = MSG(u'Objects ordered on top.')


    def action_order_bottom(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = MSG(u'Please select the objects to order on bottom.')
            context.message = message
            return

        resource.handler.order_bottom(ids)
        context.message = MSG(u'Objects ordered on bottom.')



###########################################################################
# Model
###########################################################################
class Multiple(DataType):

    def decode(self, data):
        if isinstance(data, list):
            lines = data
        else:
            lines = data.splitlines()

        return [ self.type.decode(x) for x in lines ]



class Table(File):

    class_version = '20071216'
    class_views = ['view', 'add_record', 'edit_metadata', 'history']
    class_handler = TableFile
    record_class = Record
    form = []


    @classmethod
    def get_form(cls):
        if cls.form != []:
            return cls.form
        schema = cls.class_handler.schema
        return [
            get_default_widget(datatype)(name)
            for name, datatype in schema.items()
        ]


    @classmethod
    def get_field_title(cls, name):
        for widget in cls.form:
            if widget.name == name:
                return getattr(widget, 'title', name)
        return name


    #########################################################################
    # Views
    #########################################################################
    new_instance = DBResource.new_instance
    view = TableView()
    add_record = AddRecordForm()
    edit_record = EditRecordForm()



class OrderedTable(Table):

    class_version = '20071216'
    class_title = MSG(u'Ordered Table')
    class_handler = OrderedTableFile

    # Views
    view = OrderedTableView()


