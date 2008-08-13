# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.datatypes import String
from itools.gettext import POFile, MSG
from itools.handlers import TextFile, Python as PythonFile
from itools.html import HTMLFile
from itools.stl import stl
from itools.web import STLForm, STLView
from itools.xml import XMLFile

# Import from ikaaro
from base import DBObject
from file import File
from messages import MSG_CHANGES_SAVED
from registry import register_object_class
from utils import get_parameters


###########################################################################
# Views
###########################################################################
class EditTextForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Inline')
    icon = 'edit.png'
    template = '/ui/text/edit.xml'
    schema = {
        'data': String(mandatory=True),
    }


    def get_namespace(self, resource, context):
        return {'data': resource.handler.to_str()}


    def action(self, resource, context, form):
        data = form['data']
        resource.handler.load_state_from_string(data)
        # Ok
        context.message = MSG_CHANGES_SAVED



class ViewText(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'
    template = '/ui/text/view.xml'


    def get_namespace(self, resource, context):
        return {'data': resource.handler.to_str()}



class ExternalEditForm(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'External Editor')
    icon = 'button_external.png'
    template = '/ui/text/externaledit.xml'


    def get_namespace(self, resource, context):
        # FIXME This list should be built from a txt file with all the
        # encodings, or better, from a Python module that tells us which
        # encodings Python supports.
        encodings = [
            {'value': 'utf-8', 'title': 'UTF-8', 'is_selected': True},
            {'value': 'iso-8859-1', 'title': 'ISO-8859-1',
             'is_selected': False}]

        return {'encodings': encodings}



class POEditForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    template = '/ui/PO_edit.xml'
    schema = {
        'msgid': String(mandatory=True),
        'msgstr': String(mandatory=True),
    }


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
        context.server.change_object(resource)

        # Ok
        context.message = MSG_CHANGES_SAVED



###########################################################################
# Model
###########################################################################
class Text(File):

    class_id = 'text'
    class_version = '20071216'
    class_title = MSG(u'Plain Text')
    class_description = u'Keep your notes with plain text files.'
    class_icon16 = 'icons/16x16/text.png'
    class_icon48 = 'icons/48x48/text.png'
    class_views = ['view', 'edit', 'externaledit', 'upload', 'edit_metadata',
                   'edit_state', 'history']
    class_handler = TextFile


    def get_content_type(self):
        return '%s; charset=UTF-8' % File.get_content_type(self)


    #######################################################################
    # Views
    #######################################################################
    edit = EditTextForm()
    view = ViewText()
    externaledit = ExternalEditForm()



class PO(Text):

    class_id = 'text/x-gettext-translation'
    class_version = '20071216'
    class_title = MSG(u'Message Catalog')
    class_icon16 = 'icons/16x16/po.png'
    class_icon48 = 'icons/48x48/po.png'
    class_handler = POFile

    edit = POEditForm()



class CSS(Text):

    class_id = 'text/css'
    class_version = '20071216'
    class_title = MSG(u'CSS')
    class_icon16 = 'icons/16x16/css.png'
    class_icon48 = 'icons/48x48/css.png'



class Python(Text):

    class_id = 'text/x-python'
    class_version = '20071216'
    class_title = MSG(u'Python')
    class_icon16 = 'icons/16x16/python.png'
    class_icon48 = 'icons/48x48/python.png'
    class_handler = PythonFile



class XML(Text):

    class_id = 'text/xml'
    class_version = '20071216'
    class_title = MSG(u'XML File')
    class_handler = XMLFile



class HTML(Text):

    class_id = 'text/html'
    class_version = '20071216'
    class_title = MSG(u'HTML File')
    class_handler = HTMLFile



###########################################################################
# Register
###########################################################################
register_object_class(Text)
register_object_class(Python)
register_object_class(PO)
register_object_class(CSS)
register_object_class(XML)
register_object_class(XML, format='application/xml')
register_object_class(HTML)

