# -*- coding: UTF-8 -*-
# Copyright (C) 2006 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
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

# Import from itools
from itools.datatypes import Boolean, Enumerate, Integer, String, is_datatype
from itools.csv import CSVFile
from itools.gettext import MSG
from itools.stl import stl
from itools.web import get_context

# Import from ikaaro
from forms import AutoForm, get_default_widget
from messages import *
from registry import register_object_class
from text import Text
from views import BrowseForm
from widgets import batch, table


###########################################################################
# Views
###########################################################################
class ViewCSV(BrowseForm):

    # FIXME We need different permissions for GET and POST
    access = 'is_allowed_to_edit'
    title = MSG(u'View')
    schema = {
        'ids': Integer(mandatory=True, multiple=True),
    }


    def get_namespace(self, resource, context):
        # The input parameters
        query = context.query
        start = query['batchstart']
        size = 50

        # The batch
        handler = resource.handler
        total = handler.get_nrows()

        # The table
        actions = []
        if total:
            ac = resource.get_access_control()
            if ac.is_allowed_to_edit(context.user, resource):
                actions = [('remove', u'Remove', 'button_delete',None)]

        columns = resource.get_columns()
        columns.insert(0, ('index', u''))
        rows = []
        index = start
        if handler.schema is not None:
            getter = lambda x, y: x.get_value(y)
        else:
            getter = lambda x, y: x[int(y)]

        read = 0
        length = len(handler.lines)
        while read < size and index < length:
            try:
                row = handler.get_row(index)
            except IndexError:
                index += 1
                continue
            rows.append({})
            rows[-1]['id'] = str(index)
            rows[-1]['checkbox'] = True
            # Columns
            rows[-1]['index'] = index, ';edit_row?index=%s' % index
            for column, column_title in columns[1:]:
                value = getter(row, column)
                datatype = handler.get_datatype(column)
                is_enumerate = getattr(datatype, 'is_enumerate', False)
                if is_enumerate:
                    rows[-1][column] = datatype.get_value(value)
                else:
                    rows[-1][column] = value
            index += 1
            read += 1

        # Sorting
        sortby = query['sortby']
        sortorder = query['sortorder']
        if sortby:
            rows.sort(key=itemgetter(sortby[0]), reverse=(sortorder=='down'))

        return {
            'batch': batch(context.uri, start, size, total),
            'table': table(columns, rows, sortby, sortorder, actions),
        }


    def action_remove(self, resource, context, form):
        ids = form['ids']
        resource.handler.del_rows(ids)
        # Ok
        context.message = u'Row deleted.'



class RowForm(AutoForm):

    access = 'is_allowed_to_edit'
    submit_class = 'button_ok'

    def get_schema(self, resource, context):
        schema = resource.handler.schema
        if schema is not None:
            return schema
        # Default
        schema = {}
        for name, title in resource.get_columns():
            schema[name] = String
        return schema


    def get_widgets(self, resource, context):
        schema = self.get_schema(resource, context)
        return [
            get_default_widget(schema[name])(name)
            for name, title in resource.get_columns()
        ]



class AddRowForm(RowForm):

    title = MSG(u'Add Row')
    icon = 'new.png'
    submit_value = MSG(u'Add')


    def action(self, resource, context, form):
        row = [ form[name] for name, title in resource.get_columns() ]
        row = resource.handler.add_row(row)
        # Ok
        message = MSG(u'New row added.')
        goto = ';edit_row?index=%s' % row.number
        return context.come_back(message, goto=goto)



class EditRowForm(RowForm):

    title = MSG(u'Edit row #${id}')
    submit_value = MSG(u'Change')
    query_schema = {
        'index': Integer,
    }


    def get_title(self, context):
        id = context.query['index']
        return self.title.gettext(id=id)


    def get_value(self, resource, context, name, datatype):
        id = context.query['index']
        row = resource.handler.get_row(id)
        return row.get_value(name)


    def action(self, resource, context, form):
        index = context.query['index']
        resource.handler.update_row(index, **form)
        # Ok
        context.message = MSG_CHANGES_SAVED



###########################################################################
# Model
###########################################################################
class CSV(Text):

    class_id = 'text/comma-separated-values'
    class_version = '20071216'
    class_title = MSG(u'Comma Separated Values')
    class_views = ['view', 'add_row', 'externaledit', 'upload',
                   'edit_metadata', 'history']
    class_handler = CSVFile


    def get_columns(self):
        """Returns a list of tuples with the name and title of every column.
        """
        handler = self.handler

        if handler.columns is None:
            row = None
            for row in handler.lines:
                if row is not None:
                    break
            if row is None:
                return []
            return [ (str(x), str(x)) for x in range(len(row)) ]

        columns = []
        for name in handler.columns:
            datatype = handler.schema[name]
            title = getattr(datatype, 'title', None)
            if title is None:
                title = name
            else:
                title = self.gettext(title)
            columns.append((name, title))

        return columns


    #########################################################################
    # Views
    #########################################################################
    edit_form__access__ = False

    view = ViewCSV()
    add_row = AddRowForm()
    edit_row = EditRowForm()



###########################################################################
# Register
###########################################################################
register_object_class(CSV)
register_object_class(CSV, 'text/x-comma-separated-values')
register_object_class(CSV, 'text/csv')
