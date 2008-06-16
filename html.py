# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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
from datetime import datetime

# Import from itools
from itools.datatypes import DateTime, FileName, String
from itools.handlers import File
from itools.http import Forbidden
from itools.html import (xhtml_uri, XHTMLFile, sanitize_stream, HTMLParser,
    stream_to_str_as_xhtml, stream_to_str_as_html)
from itools.stl import stl
from itools.uri import get_reference
from itools.xml import TEXT, START_ELEMENT, XMLError, XMLParser

# Import from ikaaro
from base import DBObject
from messages import *
from multilingual import Multilingual
from text import Text
from registry import register_object_class


class EpozEditable(object):
    """A mixin class for handlers implementing HTML editing.
    """

    #######################################################################
    # API
    #######################################################################
    def get_epoz_document(self):
        # Implement it in your editable handler
        raise NotImplementedError


    def get_epoz_data(self):
        document = self.get_epoz_document()
        body = document.get_body()
        if body is None:
            return None
        return body.get_content_elements()


    #######################################################################
    # User Interface
    #######################################################################
    edit_form__access__ = 'is_allowed_to_edit'
    edit_form__label__ = u'Edit'
    edit_form__sublabel__ = u'Inline'
    edit_form__icon__ = 'edit.png'
    def edit_form(self, context):
        """WYSIWYG editor for HTML documents.
        """
        data = context.get_form_value('data')
        if data:
            data = stream_to_str_as_html(XMLParser(data))
        else:
            data = self.get_epoz_data()
            # If the document has not a body (e.g. a frameset), edit as plain text
            if data is None:
                return Text.edit_form(self, context)
            data = stream_to_str_as_html(data)

        # Edit with a rich text editor
        namespace = {}
        namespace['timestamp'] = DateTime.encode(datetime.now())
        namespace['rte'] = self.get_rte(context, 'data', data)

        handler = self.get_object('/ui/html/edit.xml')
        return stl(handler, namespace)


    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context, sanitize=False):
        timestamp = context.get_form_value('timestamp', type=DateTime)
        if timestamp is None:
            return context.come_back(MSG_EDIT_CONFLICT)
        document = self.get_epoz_document()
        if document.timestamp is not None and timestamp < document.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        # Sanitize
        new_body = context.get_form_value('data')
        try:
            new_body = list(XMLParser(new_body,
                                      {None: 'http://www.w3.org/1999/xhtml'}))
        except XMLError:
            return context.come_back(u'Invalid HTML code.', keep=['data'])
        if sanitize:
            new_body = sanitize_stream(new_body)
        # "get_epoz_document" is to set in your editable handler
        old_body = document.get_body()
        events = (document.events[:old_body.start+1] + new_body
                  + document.events[old_body.end:])
        # Change
        document.set_events(events)
        context.server.change_object(self)

        return context.come_back(MSG_CHANGES_SAVED)




class WebPage(EpozEditable, Multilingual, Text):

    class_id = 'webpage'
    class_version = '20071217'
    class_title = u'Web Page'
    class_description = u'Create and publish a Web Page.'
    class_icon16 = 'icons/16x16/html.png'
    class_icon48 = 'icons/48x48/html.png'
    class_views = [['view'],
                   ['edit_form', 'externaledit', 'upload_form'],
                   ['edit_metadata_form'],
                   ['state_form'],
                   ['history_form']]
    class_handler = XHTMLFile


    @classmethod
    def get_metadata_schema(cls):
        schema = Text.get_metadata_schema()
        # FIXME Needed by the upgrade code from 0.16 to 0.20
        schema['language'] = String
        return schema


    def get_links(self):
        base = self.get_abspath()

        languages = self.get_site_root().get_property('website_languages')
        links = []
        for language in languages:
            handler = self.get_handler(language=language)
            for event in handler.events:
                type, value, line = event
                if type != START_ELEMENT:
                    continue
                tag_uri, tag_name, attributes = value
                if tag_uri != xhtml_uri:
                    continue
                if tag_name == 'a':
                    value = attributes.get((xhtml_uri, 'href'))
                elif tag_name == 'img':
                    value = attributes.get((xhtml_uri, 'src'))
                else:
                    continue
                if value is None:
                    continue
                uri = get_reference(value)
                if uri.scheme or uri.authority or not uri.path:
                    continue
                uri = base.resolve(uri.path)
                uri = str(uri)
                links.append(uri)
        return links


    #######################################################################
    # API
    #######################################################################
    def to_text(self):
        text = [ x.to_text() for x in self.get_handlers() ]
        return ' '.join(text)


    GET__mtime__ = None
    def GET(self, context):
        method = self.get_firstview()
        # Check access
        if method is None:
            raise Forbidden
        # Redirect
        return context.uri.resolve2(';%s' % method)


    def is_empty(self):
        """Test if XML doc is empty
        """
        body = self.handler.get_body()
        if body is None:
            return True
        for type, value, line in body.events:
            if type == TEXT:
                if value.replace('&nbsp;', '').strip():
                    return False
            elif type == START_ELEMENT:
                tag_uri, tag_name, attributes = value
                if tag_name == 'img':
                    return False
        return True


    def get_content_type(self):
        return 'application/xhtml+xml; charset=UTF-8'


    #######################################################################
    # UI / New Instance
    #######################################################################
    @staticmethod
    def new_instance_form(cls, context):
        return DBObject.new_instance_form(cls, context)


    @staticmethod
    def new_instance(cls, container, context):
        return DBObject.new_instance(cls, container, context)


    #######################################################################
    # UI / View
    #######################################################################
    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    view__title__ = u'View'
    def view(self, context):
        namespace = {}
        body = self.handler.get_body()
        if body is None:
            namespace['text'] = None
        else:
            namespace['text'] = body.get_content_elements()

        handler = self.get_object('/ui/html/view.xml')
        return stl(handler, namespace)


    #######################################################################
    # UI / Edit / Inline
    #######################################################################
    def get_epoz_document(self):
        return self.handler



###########################################################################
# Register
###########################################################################
register_object_class(WebPage)
register_object_class(WebPage, format='application/xhtml+xml')
