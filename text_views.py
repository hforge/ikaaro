# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Standard Library
from operator import itemgetter

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Integer, String
from itools.gettext import MSG
from itools.web import STLForm, STLView, INFO

# Import from ikaaro
from autoform import AutoForm, get_default_widget
from buttons import RemoveButton
from file_views import File_Edit
from forms import Textarea, TextField
import messages
from views import BrowseForm


class Text_Edit(File_Edit):

    icon = 'edit.png'

    data = TextField('data', datatype=String)
    data.widget = Textarea(rows=19, cols=69)
    data.title = MSG(u'Content')


    def get_value(self, resource, context, name, datatype):
        if name == 'data':
            return resource.handler.to_str()
        return File_Edit.get_value(self, resource, context, name, datatype)


    def action(self, resource, context, form):
        File_Edit.action(self, resource, context, form)
        if form['file'] is None:
            data = form['data']
            resource.handler.load_state_from_string(data)



class Text_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'
    template = '/ui/text/view.xml'


    def get_namespace(self, resource, context):
        return {'data': resource.handler.to_str()}



class PO_Edit(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    template = '/ui/PO_edit.xml'
    schema = {
        'msgid': String(mandatory=True),
        'msgstr': String(mandatory=True),
    }


    def get_namespace(self, resource, context):
        # Get the translation units (all but the header)
        handler = resource.handler
        units = handler.get_units()
        units.sort(key=lambda x: x.source)
        if units and ''.join(units[0].source) == '':
            units = units[1:]

        # Total, index, etc.
        total = len(units)
        index = context.get_form_value('messages_index', default='1')
        index = int(index)
        previous = max(index - 1, 1)
        next = min(index + 1, total)

        # Msgid and msgstr
        if units:
            unit = units[index-1]
            msgid = ''.join(unit.source)
            msgstr = ''.join(unit.target)
        else:
            msgid = None
            msgstr = None

        # Ok
        uri = context.uri
        return {
            'messages_total': total,
            'messages_index': index,
            'messages_first': uri.replace(messages_index='1'),
            'messages_last': uri.replace(messages_index=str(total)),
            'messages_previous': uri.replace(messages_index=str(previous)),
            'messages_next': uri.replace(messages_index=str(next)),
            'msgid': msgid,
            'msgstr': msgstr}


    def action(self, resource, context, form):
        msgid = form['msgid'].replace('\r', '')
        msgstr = form['msgstr'].replace('\r', '')
        resource.handler.set_message(msgid, msgstr)
        # Events, change
        context.change_resource(resource)

        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CSV_View(BrowseForm):

    # FIXME We need different permissions for GET and POST
    access = 'is_allowed_to_edit'
    title = MSG(u'View')
    schema = {
        'ids': Integer(mandatory=True, multiple=True),
    }


    def get_items(self, resource, context):
        return list(resource.handler.get_rows())


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        if sort_by:
            sort_by = int(sort_by)
            items.sort(key=itemgetter(sort_by), reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    def get_table_columns(self, resource, context):
        columns = resource.get_columns()
        columns.insert(0, ('checkbox', None))
        columns.insert(1, ('index', None))
        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.number, False
        elif column == 'index':
            index = item.number
            return index, ';edit_row?index=%s' % index

        # A value from the schema
        handler = resource.handler
        datatype = handler.get_datatype(column)
        if handler.schema is None:
            value = item[int(column)]
        else:
            value = item.get_value(column)

        # Columns
        is_enumerate = getattr(datatype, 'is_enumerate', False)
        if is_enumerate:
            return datatype.get_value(value)
        return value


    table_actions = [RemoveButton]


    def action_remove(self, resource, context, form):
        ids = form['ids']
        resource.handler.del_rows(ids)
        # Ok
        context.message = INFO(u'Row deleted.')



class RowForm(AutoForm):

    access = 'is_allowed_to_edit'

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
            get_default_widget(schema[name])(name, title=title)
            for name, title in resource.get_columns() ]



class CSV_AddRow(RowForm):

    title = MSG(u'Add Row')
    icon = 'new.png'
    submit_value = MSG(u'Add')


    def action(self, resource, context, form):
        row = [ form[name] for name, title in resource.get_columns() ]
        row = resource.handler.add_row(row)
        # Ok
        message = INFO(u'New row added.')
        goto = ';edit_row?index=%s' % row.number
        return context.come_back(message, goto=goto)



class CSV_EditRow(RowForm):

    title = MSG(u'Edit row #{id}')
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
        context.message = messages.MSG_CHANGES_SAVED

