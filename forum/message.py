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
from itools.xml import XMLParser
from itools.html import HTMLParser, sanitize_stream, xhtml_uri, XHTMLFile

# Import from ikaaro
from ikaaro.messages import MSG_CHANGES_SAVED
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
    class_title = u"Message"
    class_description = u"Message in a thread"
    class_views = [['edit_form'], ['history_form']]


    @staticmethod
    def _make_object(cls, folder, name, data):
        WebPage._make_object(cls, folder, name)
        # The message
        document = build_message(data)
        folder.set_handler(name, document)


    # Was already indexed at the thread level
    def to_text(self):
        return u''


    edit__access__ = 'is_admin'
    def edit(self, context):
        WebPage.edit(self, context, sanitize=True)

        return context.come_back(MSG_CHANGES_SAVED, goto='../;view')



register_object_class(Message)
