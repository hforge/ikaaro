# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.datatypes import FileName
from itools.gettext import MSG
from itools.html import HTMLParser, sanitize_stream, XHTMLFile

# Import from ikaaro
from ikaaro.messages import *
from ikaaro.registry import register_object_class
from ikaaro.html import WebPage


def build_message(data):
    document = XHTMLFile()
    new_body = HTMLParser(data)
    new_body = sanitize_stream(new_body)
    old_body = document.get_body()
    document.events = (document.events[:old_body.start+1]
                       + new_body
                       + document.events[old_body.end:])
    return document



class Message(WebPage):

    class_id = 'ForumMessage'
    class_version = '20071216'
    class_title = MSG(u'Message')
    class_description = u"Message in a thread"
    class_views = ['edit_form', 'history_form']


    @staticmethod
    def _make_object(cls, folder, name, data, language):
        WebPage._make_object(cls, folder, name)
        # The message
        document = build_message(data)
        folder.set_handler('%s.xhtml.%s' % (name, language), document)


    def get_context_menu_base(self):
        # Show actions of the forum
        return self.parent.parent


    def get_catalog_fields(self):
        # text field was already indexed at the thread level
        return [ x for x in WebPage.get_catalog_fields(self)
                 if x.name != 'text' ]


    edit__access__ = 'is_admin'
    def edit(self, context):
        WebPage.edit(self, context, sanitize=True)

        # Change, index parent
        context.server.change_object(self.parent)

        return context.come_back(MSG_CHANGES_SAVED, goto='../;view')



register_object_class(Message)
