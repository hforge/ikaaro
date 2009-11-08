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
from cgi import escape
from operator import itemgetter

# Import from itools
from itools.core import thingy_property, thingy_lazy_property
from itools.datatypes import Enumerate, Integer, String
from itools.gettext import MSG
from itools.web import STLForm, STLView, INFO
from itools.web import input_field, integer_field, multiple_choice_field
from itools.web import textarea_field

# Import from ikaaro
from autoform import AutoForm, get_default_field
from buttons import RemoveButton
from file_views import File_Edit
import messages
from utils import get_parameters
from views import BrowseForm


class Text_Edit(File_Edit):

    icon = 'edit.png'

    data = textarea_field('data', datatype=String, rows=19, cols=69)
    data.title = MSG(u'Content')


    def get_value(self, field):
        if field.name == 'data':
            return self.resource.handler.to_str()
        return super(Text_Edit, self).get_value(field)


    def action(self):
        super(Text_Edit, self).action()
        if self.file.value is None:
            data = self.data.value
            self.resource.handler.load_state_from_string(data)



class Text_View(STLView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'View')
    icon = 'view.png'
    template = 'text/view.xml'


    def data(self):
        return self.resource.handler.to_str()



class Text_ExternalEdit(STLView):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'External Editor')
    icon = 'external.png'
    template = 'text/externaledit.xml'


    def encodings(self):
        # FIXME This list should be built from a txt file with all the
        # encodings, or better, from a Python module that tells us which
        # encodings Python supports.
        return [
            {'value': 'utf-8', 'title': 'UTF-8', 'is_selected': True},
            {'value': 'iso-8859-1', 'title': 'ISO-8859-1',
             'is_selected': False}]



class PO_Edit(STLForm):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Edit')
    template = '/ui/PO_edit.xml'
    schema = {
        'msgid': String(mandatory=True),
        'msgstr': String(mandatory=True)}


    def get_namespace(self, resource, context):
        # Get the messages, all but the header
        handler = resource.handler
        msgids = [ x for x in handler.get_msgids() if x.strip() ]

        # Set total
        total = len(msgids)
        namespace = {}
        namespace['messages_total'] = str(total)

        # Set the index
        parameters = get_parameters('messages', index='1')
        index = parameters['index']
        namespace['messages_index'] = index
        index = int(index)

        # Set first, last, previous and next
        uri = context.uri
        messages_first = uri.replace(messages_index='1')
        namespace['messages_first'] = messages_first
        messages_last = uri.replace(messages_index=str(total))
        namespace['messages_last'] = messages_last
        previous = max(index - 1, 1)
        messages_previous = uri.replace(messages_index=str(previous))
        namespace['messages_previous'] = messages_previous
        next = min(index + 1, total)
        messages_next = uri.replace(messages_index=str(next))
        namespace['messages_next'] = messages_next

        # Set msgid and msgstr
        if msgids:
            msgids.sort()
            msgid = msgids[index-1]
            namespace['msgid'] = escape(msgid)
            msgstr = handler.get_msgstr(msgid)
            msgstr = escape(msgstr)
            namespace['msgstr'] = msgstr
        else:
            namespace['msgid'] = None

        return namespace


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
    view_title = MSG(u'View')

    ids = multiple_choice_field(datatype=Integer, required=True)


    @thingy_lazy_property
    def all_items(self):
        return list(self.resource.handler.get_rows())


    @thingy_lazy_property
    def items(self):
        items = self.all_items

        # Sort
        sort_by = self.sort_by.value
        reverse = self.reverse.value
        if sort_by:
            sort_by = int(sort_by)
            items = sorted(items, key=itemgetter(sort_by), reverse=reverse)

        # Batch
        start = self.batch_start.value
        size = self.batch_size.value
        return items[start:start+size]


    def get_table_columns(self):
        columns = self.resource.get_columns()
        columns.insert(0, ('checkbox', None))
        columns.insert(1, ('index', None))
        return columns


    def get_item_value(self, item, column):
        if column == 'checkbox':
            return item.number, False
        elif column == 'index':
            index = item.number
            return index, ';edit_row?index=%s' % index

        # A value from the schema
        handler = self.resource.handler
        datatype = handler.get_datatype(column)
        if handler.schema is None:
            value = item[int(column)]
        else:
            value = item.get_value(column)

        # Columns
        if issubclass(datatype, Enumerate):
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


    def get_field_names(self):
        resource = self.resource

        schema = resource.handler.schema
        if schema is None:
            return [ name for name, title in resource.get_columns() ]

        return schema.keys()


    def get_field(self, name):
        resource = self.resource

        schema = resource.handler.schema
        if schema is None:
            return input_field(name)

        # The title comes from the columns
        for column_name, column_title in resource.get_columns():
            if column_name == name:
                title = column_title
                break
        else:
            title = None

        datatype = schema[name]
        field = get_default_field(datatype)
        field = field(name, datatype=datatype, title=title)
        return field



class CSV_AddRow(RowForm):

    view_title = MSG(u'Add Row')
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

    index = integer_field(source='query')


    def get_field_names(self):
        field_names = super(CSV_EditRow, self).get_field_names()
        return ['index'] + field_names


    @thingy_lazy_property
    def row(self):
        return self.resource.handler.get_row(self.index.value)


    @thingy_property
    def view_title(self):
        title = MSG(u'Edit row #{id}')
        return title.gettext(id=self.index.value)


    def get_value(self, field):
        return self.row.get_value(field.name)


    def action(self, resource, context, form):
        index = self.index.value
        resource.handler.update_row(index, **form)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED
        context.redirect()

