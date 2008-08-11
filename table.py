# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from operator import itemgetter

# Import from itools
from itools.csv import Record, UniqueError, Table as TableFile
from itools.datatypes import DataType, is_datatype
from itools.datatypes import Integer, Enumerate, Date, Tokens
from itools.gettext import MSG
from itools.http import Forbidden
from itools.stl import stl
from itools.web import FormError, STLView, get_context

# Import from ikaaro
from base import DBObject
from file import File
from forms import AutoForm, get_default_widget, ReadOnlyWidget
from messages import *
from registry import register_object_class
from views import BrowseForm
from widgets import batch, table


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

    def get_widgets(self, resource):
        return resource.get_form()


    def get_namespace(self, resource, context):
        # The input parameters
        query = context.query
        start = query['batchstart']
        size = 50

        # The batch
        handler = resource.handler
        total = handler.get_n_records()

        # The table
        actions = []
        if total:
            ac = resource.get_access_control()
            if ac.is_allowed_to_edit(context.user, resource):
                message_utf8 = MSG_DELETE_SELECTION.gettext().encode('utf_8')
                actions = [('del_record_action', u'Remove', 'button_delete',
                            'return confirmation("%s");' % message_utf8)]

        fields = [('index', u'id')]
        widgets = self.get_widgets(resource)
        for widget in widgets:
            fields.append((widget.name, getattr(widget, 'title', widget.name)))
        records = []

        for record in handler.get_records():
            id = record.id
            records.append({})
            records[-1]['id'] = str(id)
            records[-1]['checkbox'] = True
            # Fields
            records[-1]['index'] = id, ';edit_record_form?id=%s' % id
            for field, field_title in fields[1:]:
                value = handler.get_value(record, field)
                datatype = handler.get_datatype(field)

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
                    records[-1][field] = datatype.get_value(value)
                else:
                    records[-1][field] = value

                if multiple is True or is_tokens:
                    records[-1][field] = (records[-1][field], rmultiple)
        # Sorting
        sortby = query['sortby']
        sortorder = query['sortorder']
        if sortby:
            reverse = (sortorder == 'down')
            records.sort(key=itemgetter(sortby[0]), reverse=reverse)

        records = records[start:start+size]
        for record in records:
            for field, field_title in fields[1:]:
                if isinstance(record[field], tuple):
                    if record[field][1] is True:
                        record[field] = '%s [...]' % record[field][0]
                    else:
                        record[field] = record[field][0]

        return {
            'batch': batch(context.uri, start, size, total),
            'table': table(fields, records, [sortby], sortorder, actions),
        }


    #######################################################################
    # Form Actions
    #######################################################################
    def del_record_action(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)

        context.message = u'Record deleted.'



class AddRecordForm(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Add')
    icon = 'new.png'

    form_title = MSG(u'Add a new record')
    submit_value = MSG(u'Add')
    submit_class = 'button_ok'


    def get_schema(self, resource, context):
        return resource.handler.schema


    def get_widgets(self, resource):
        return resource.get_form()


    def action(self, resource, context, form):
        schema = self.get_schema(resource)
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
    form_title = MSG(u'Edit record ${id}')
    submit_value = MSG(u'Change')
    submit_class = 'button_ok'
    query_schema = {'id': Integer}


    def method(self, name):
        context = get_context()
        # Get the record
        resource = context.resource
        id = context.query['id']
        record = resource.get_handler().get_record(id)
        # Return the value
        return getattr(record, name)


    def get_schema(self, resource, context):
        return resource.get_handler().schema


    def get_widgets(self, resource):
        return resource.get_form()


    def get_form_title(self):
        id = get_context().get_form_value('id')
        return self.form_title.gettext(id=id)


    def action(self, resource, context, form):
        id = context.query.get('id')
        if id is None:
            context.message = MSG_MISSING_OR_INVALID
            return

        # check form
        check_fields = {}
        for widget in self.get_form():
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[widget.name] = datatype

        try:
            form = context.check_form_input(check_fields)
        except FormError:
            context.message = MSG_MISSING_OR_INVALID
            return

        # Get the record
        record = {}
        for widget in self.get_form():
            datatype = self.handler.get_datatype(widget.name)
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
            self.handler.update_record(id, **record)
        except UniqueError, error:
            title = self.get_field_title(error.name)
            context.message = str(error) % (title, error.value)
        except ValueError, error:
            title = self.get_field_title(error.name)
            message = MSG(u'Error: $message')
            context.message = message.gettext(message=strerror)
        else:
            context.message = MSG_CHANGES_SAVED


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

    class_id = 'table'
    class_version = '20071216'
    class_title = MSG(u'Table')
    class_views = ['view', 'add_record', 'edit_metadata', 'history']
    class_handler = TableFile
    record_class = Record
    form = []


    @classmethod
    def get_form(cls):
        if cls.form != []:
            return cls.form
        form = []
        for key, value in cls.class_handler.schema.items():
            widget = get_default_widget(value)
            form.append(widget(key))
        return form


    @classmethod
    def get_field_title(cls, name):
        for widget in cls.form:
            if widget.name == name:
                return getattr(widget, 'title', name)
        return name


    #########################################################################
    # Views
    #########################################################################
    new_instance = DBObject.new_instance
    view = TableView()
    add_record = AddRecordForm()
    edit_record = EditRecordForm()



###########################################################################
# Register
###########################################################################
register_object_class(Table)
