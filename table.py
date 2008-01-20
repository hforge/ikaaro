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
from operator import itemgetter
from string import Template

# Import from itools
from itools.csv import Record, Table as TableFile
from itools.datatypes import (DataType, Integer, is_datatype, Enumerate, Date,
                              Tokens)
from itools.stl import stl
from itools.web import FormError

# Import from ikaaro
from base import DBObject
from file import File
from forms import get_default_widget
from messages import *
from registry import register_object_class
import widgets



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
    class_title = u'Table'
    class_views = [['view'],
                   ['add_record_form'],
                   ['edit_metadata_form'],
                   ['history_form']]
    class_handler = TableFile

    record_class = Record


    def GET(self, context):
        method = self.get_firstview()
        # Check access
        if method is None:
            raise Forbidden
        # Redirect
        return context.uri.resolve2(';%s' % method)


    #########################################################################
    # User Interface
    #########################################################################

    @staticmethod
    def new_instance_form(cls, context):
        # Use the default form
        return DBObject.new_instance_form(cls, context)


    @staticmethod
    def new_instance(cls, container, context):
        return DBObject.new_instance(cls, container, context)


    #########################################################################
    # User Interface
    #########################################################################
    edit_form__access__ = False


    #########################################################################
    # View
    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    def view(self, context):
        namespace = {}

        # The input parameters
        start = context.get_form_value('batchstart', type=Integer, default=0)
        size = 50

        # The batch
        total = self.handler.get_n_records()
        namespace['batch'] = widgets.batch(context.uri, start, size, total,
                                           self.gettext)

        # The table
        actions = []
        if total:
            ac = self.get_access_control()
            if ac.is_allowed_to_edit(context.user, self):
                actions = [('del_record_action', u'Remove', 'button_delete',
                            None)]

        fields = [('index', u'id')]
        for widget in self.handler.form:
            fields.append((widget.name, getattr(widget, 'title', widget.name)))
        records = []

        for record in self.handler.get_records():
            id = record.id
            records.append({})
            records[-1]['id'] = str(id)
            records[-1]['checkbox'] = True
            # Fields
            records[-1]['index'] = id, ';edit_record_form?id=%s' % id
            for field, field_title in fields[1:]:
                value = self.handler.get_value(record, field)
                datatype = self.handler.get_datatype(field)

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
        sortby = context.get_form_value('sortby')
        sortorder = context.get_form_value('sortorder', 'up')
        if sortby:
            records.sort(key=itemgetter(sortby), reverse=(sortorder=='down'))

        records = records[start:start+size]
        for record in records:
            for field, field_title in fields[1:]:
                if isinstance(record[field], tuple):
                    if record[field][1] is True:
                        record[field] = '%s [...]' % record[field][0]
                    else:
                        record[field] = record[field][0]

        namespace['table'] = widgets.table(fields, records, [sortby],
                                           sortorder, actions,
                                           gettext=self.gettext)

        handler = self.get_object('/ui/table/view.xml')
        return stl(handler, namespace)


    del_record_action__access__ = 'is_allowed_to_edit'
    def del_record_action(self, context):
        ids = context.get_form_values('ids', type=Integer)
        for id in ids:
            self.handler.del_record(id)

        message = u'Record deleted.'
        return context.come_back(message)


    #########################################################################
    # Add
    add_record_form__access__ = 'is_allowed_to_edit'
    add_record_form__label__ = u'Add'
    def add_record_form(self, context):
        namespace = {}
        fields = []
        for widget in self.handler.form:
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is False:
                value = context.get_form_value(widget.name) \
                        or getattr(datatype, 'default', None)
            else:
                value = context.get_form_values(widget.name) \
                        or getattr(datatype, 'default', None)

            is_mandatory = getattr(datatype, 'mandatory', False)
            field = {}
            field['name'] = widget.name
            title = getattr(widget, 'title', widget.name)
            field['title'] = self.gettext(title)
            field['mandatory'] = is_mandatory
            field['multiple'] = getattr(datatype, 'multiple', False)
            field['is_date'] = is_datatype(datatype, Date)
            field['widget'] = widget.to_html(datatype, value)
            # Class
            cls = []
            if is_mandatory:
                cls.append('field_required')
            if context.has_form_value(widget.name):
                if is_mandatory and not value:
                    cls.append('missing')
                elif value and not datatype.is_valid(value):
                    cls.append('missing')
            field['class'] = u' '.join(cls) or None
            # Append
            fields.append(field)
        namespace['fields'] = fields

        handler = self.get_object('/ui/table/add_record.xml')
        return stl(handler, namespace)



    add_record_action__access__ = 'is_allowed_to_edit'
    def add_record_action(self, context):
        # check form
        check_fields = {}
        for name in self.handler.schema.keys():
            datatype = self.handler.get_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[name] = datatype

        try:
            form = context.check_form_input(check_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID,
                                     keep=context.get_form_keys())

        record = {}
        for name in self.handler.schema.keys():
            datatype = self.handler.get_datatype(name)
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
            self.handler.add_record(record)
            message = u'New record added.'
        except ValueError, strerror:
            template = Template(self.gettext(u'Error: $message'))
            message = template.substitute(message=strerror)

        goto = context.uri.resolve2('../;add_record_form')
        return context.come_back(message, goto=goto)



    #########################################################################
    # Edit
    edit_record_form__access__ = 'is_allowed_to_edit'
    def edit_record_form(self, context):
        # Get the record
        id = context.get_form_value('id', type=Integer)
        record = self.handler.get_record(id)

        # Build the namespace
        namespace = {}
        namespace['id'] = id

        fields = []
        for widget in self.handler.form:
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is False:
                value = context.get_form_value(widget.name) \
                        or self.handler.get_value(record, widget.name)
                if is_datatype(datatype, Tokens):
                    value = ' '.join(value) # remove parenthesis
            else:
                value = context.get_form_values(widget.name) \
                        or self.handler.get_value(record, widget.name)

            if is_datatype(datatype, Enumerate) is False \
                    and getattr(datatype, 'multiple', False) is True:
                if isinstance(value, list) is True:
                    if value and isinstance(value[0], str) is False:
                        # get value from the record
                        for index in (range(len(value))):
                            value[index] = datatype.encode(value[index])
                    value = '\n'.join(value)
                else:
                    value = datatype.encode(value)

            is_mandatory = getattr(datatype, 'mandatory', False)
            field = {}
            title = getattr(widget, 'title', widget.name)
            field['title'] = self.gettext(title)
            field['mandatory'] = is_mandatory
            field['multiple'] = getattr(datatype, 'multiple', False)
            field['is_date'] = is_datatype(datatype, Date)
            field['widget'] = widget.to_html(datatype, value)
            # Class
            cls = []
            if is_mandatory:
                cls.append('field_required')
            if context.has_form_value(widget.name):
                form_value = context.get_form_value(widget.name)
                if is_mandatory and not form_value:
                    cls.append('missing')
                elif form_value and not datatype.is_valid(form_value):
                    cls.append('missing')
            field['class'] = u' '.join(cls) or None
            # Append
            fields.append(field)
        namespace['fields'] = fields
        handler = self.get_object('/ui/table/edit_record.xml')
        return stl(handler, namespace)


    edit_record__access__ = 'is_allowed_to_edit'
    def edit_record(self, context):
        # check form
        check_fields = {}
        for widget in self.handler.form:
            datatype = self.handler.get_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[widget.name] = datatype

        try:
            form = context.check_form_input(check_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID,
                                     keep=context.get_form_keys())

        # Get the record
        id = context.get_form_value('id', type=Integer)
        record = {}
        for widget in self.handler.form:
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
            message = MSG_CHANGES_SAVED
        except ValueError, strerror:
            template = Template(self.gettext(u'Error: $message'))
            message = template.substitute(message=strerror)

        goto = context.uri.resolve2('../;edit_record_form')
        return context.come_back(message, goto=goto, keep=['id'])


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self):
        File.update_20071215(self)


    def update_20071216(self):
        File.update_20071216(self)


register_object_class(Table)
