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
from itools.datatypes import Boolean, Enumerate, Integer, is_datatype
from itools.csv import CSVFile
from itools.stl import stl

# Import from ikaaro
from messages import *
from registry import register_object_class
from text import Text
from views import BrowseForm
import widgets


###########################################################################
# Views
###########################################################################
class ViewCSV(BrowseForm):

    # FIXME We need different permissions for GET and POST
    access = 'is_allowed_to_edit'
    __label__ = u'View'
    schema = {
        'ids': Integer(mandatory=True),
    }


    def get_namespace(self, model, context, query):
        namespace = {}

        handler = model.handler

        # The input parameters
        start = query['batchstart']
        size = 50

        # The batch
        total = handler.get_nrows()
        namespace['batch'] = widgets.batch(context.uri, start, size, total,
                                           model.gettext)

        # The table
        actions = []
        if total:
            ac = model.get_access_control()
            if ac.is_allowed_to_edit(context.user, model):
                actions = [('action', u'Remove', 'button_delete',None)]

        columns = model.get_columns()
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
            rows[-1]['index'] = index, ';edit_row_form?index=%s' % index
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

        namespace['table'] = widgets.table(columns, rows, sortby, sortorder,
                                           actions)

        return namespace


    def action(self, model, context, form):
        ids = form['ids']
        model.handler.del_rows(ids)
        # Ok
        context.message = u'Row deleted.'



###########################################################################
# Model
###########################################################################
class CSV(Text):

    class_id = 'text/comma-separated-values'
    class_version = '20071216'
    class_title = u'Comma Separated Values'
    class_views = [['view'],
                   ['add_row_form'],
                   ['externaledit', 'upload_form'],
                   ['edit_metadata'],
                   ['history']]
    class_handler = CSVFile


    #########################################################################
    # User Interface
    #########################################################################
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
    # User Interface
    #########################################################################
    edit_form__access__ = False

    view = ViewCSV()


    #########################################################################
    # Add
    add_row_form__access__ = 'is_allowed_to_edit'
    add_row_form__label__ = u'Add'
    add_row_form__icon__ = 'new.png'
    def add_row_form(self, context):
        namespace = {}
        handler = self.handler

        columns = []
        for name, title in self.get_columns():
            column = {}
            column['name'] = name
            column['title'] = title
            column['value'] = None
            # Enumerates, use a selection box
            datatype = handler.get_datatype(name)
            column['is_input'] = False
            column['is_enumerate'] = False
            column['is_boolean'] = False
            if is_datatype(datatype, Enumerate):
                column['is_enumerate'] = True
                column['options'] = datatype.get_namespace(None)
            elif is_datatype(datatype, Boolean):
                column['is_boolean'] = True
            else:
                column['is_input'] = True
            # Append
            columns.append(column)
        namespace['columns'] = columns

        handler = self.get_object('/ui/csv/add_row.xml')
        return stl(handler, namespace)


    add_row_action__access__ = 'is_allowed_to_edit'
    def add_row_action(self, context):
        handler = self.handler
        row = []
        for name, title in self.get_columns():
            datatype = handler.get_datatype(name)
            value = context.get_form_value(name, type=datatype)
            row.append(value)

        handler.add_row(row)

        message = u'New row added.'
        return context.come_back(message)


    #########################################################################
    # Edit
    edit_row_form__access__ = 'is_allowed_to_edit'
    def edit_row_form(self, context):
        handler = self.handler
        # Get the row
        index = context.get_form_value('index', type=Integer)
        row = handler.get_row(index)

        # Build the namespace
        namespace = {}
        namespace['index'] = index
        # Columns
        columns = []
        for name, title in self.get_columns():
            column = {}
            column['name'] = name
            column['title'] = title
            value = row.get_value(name)
            # Enumerates, use a selection box
            datatype = handler.get_datatype(name)
            column['is_input'] = False
            column['is_enumerate'] = False
            column['is_boolean'] = False
            if is_datatype(datatype, Enumerate):
                column['is_enumerate'] = True
                column['options'] = datatype.get_namespace(value)
            elif is_datatype(datatype, Boolean):
                column['is_boolean'] = True
                column['is_selected'] = value
            else:
                column['is_input'] = True
                column['value'] = datatype.encode(value)
            # Append
            columns.append(column)
        namespace['columns'] = columns

        handler = self.get_object('/ui/csv/edit_row.xml')
        return stl(handler, namespace)


    edit_row__access__ = 'is_allowed_to_edit'
    def edit_row(self, context):
        handler = self.handler
        # Get the row
        index = context.get_form_value('index', type=Integer)

        kw = {}
        for name, title in self.get_columns():
            datatype = handler.get_datatype(name)
            kw[name] = context.get_form_value(name, type=datatype)
        handler.update_row(index, **kw)

        return context.come_back(MSG_CHANGES_SAVED)



register_object_class(CSV)
register_object_class(CSV, 'text/x-comma-separated-values')
register_object_class(CSV, 'text/csv')
