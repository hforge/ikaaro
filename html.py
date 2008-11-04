# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.datatypes import DateTime
from itools.gettext import MSG
from itools.handlers import merge_dics
from itools.html import xhtml_uri, XHTMLFile
from itools.uri import get_reference
from itools.web import BaseView
from itools.xml import TEXT, START_ELEMENT

# Import from ikaaro
import messages
from forms import HTMLBody
from forms import title_widget, description_widget, subject_widget
from forms import rte_widget, timestamp_widget
from multilingual import Multilingual
from text import Text
from registry import register_resource_class
from resource_ import DBResource
from resource_views import DBResource_Edit


def is_edit_conflict(resource, context, timestamp):
    if timestamp is None:
        context.message = messages.MSG_EDIT_CONFLICT
        return True
    handler = resource.handler
    if handler.timestamp is not None and timestamp < handler.timestamp:
        # Conlicft unless we are overwriting our own work
        last_author = resource.get_last_author()
        if last_author != context.user.name:
            root = context.root
            try:
                user = root.get_user(last_author)
                user = user.get_title()
            except LookupError:
                user = last_author
            context.message = messages.MSG_EDIT_CONFLICT2(user=user)
            return True
    return False


###########################################################################
# Views
###########################################################################
class WebPage_View(BaseView):
    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'


    def GET(self, resource, context):
        return resource.get_epoz_data()



class HTMLEditView(DBResource_Edit):
    """WYSIWYG editor for HTML documents.
    """
    schema = merge_dics(DBResource_Edit.schema,
                        data=HTMLBody, timestamp=DateTime(readonly=True))
    widgets = [title_widget, rte_widget, description_widget, subject_widget,
               timestamp_widget]


    def get_value(self, resource, context, name, datatype):
        if name == 'data':
            return resource.get_epoz_data()
        elif name == 'timestamp':
            return datetime.now()
        return DBResource_Edit.get_value(self, resource, context, name,
                                         datatype)


    def action(self, resource, context, form):
        if is_edit_conflict(resource, context, form['timestamp']):
            return

        # Properties
        DBResource_Edit.action(self, resource, context, form)

        # Body
        new_body = form['data']
        resource.handler.set_body(new_body)

        # Ok
        context.message = messages.MSG_CHANGES_SAVED



###########################################################################
# Model
###########################################################################
class EpozEditable(object):
    """A mixin class for handlers implementing HTML editing.
    """

    edit = HTMLEditView()


    def get_epoz_document(self):
        # Implement it in your editable handler
        raise NotImplementedError


    def get_epoz_data(self):
        document = self.get_epoz_document()
        body = document.get_body()
        if body is None:
            return None
        return body.get_content_elements()




class WebPage(EpozEditable, Multilingual, Text):

    class_id = 'webpage'
    class_version = '20080902'
    class_title = MSG(u'Web Page')
    class_description = MSG(u'Create and publish a Web Page.')
    class_icon16 = 'icons/16x16/html.png'
    class_icon48 = 'icons/48x48/html.png'
    class_views = ['view', 'edit', 'externaledit', 'upload', 'backlinks',
                   'edit_state', 'history']
    class_handler = XHTMLFile


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
        return u' '.join(text)


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
    # UI
    #######################################################################
    new_instance = DBResource.new_instance
    view = WebPage_View()

    def get_epoz_document(self):
        return self.handler


    #######################################################################
    # Update
    #######################################################################
    def update_20080902(self):
        def fix_links(stream):
            for event in stream:
                type, value, line = event
                if type != START_ELEMENT:
                    yield event
                    continue
                tag_uri, tag_name, attributes = value
                if tag_uri != xhtml_uri:
                    yield event
                    continue
                if tag_name != 'img':
                    yield event
                    continue
                value = attributes.get((None, 'src'))
                if value is None:
                    yield event
                    continue
                uri = get_reference(value)
                if uri.scheme or uri.authority or not uri.path:
                    yield event
                    continue
                if value.startswith('/ui/'):
                    yield event
                    continue
                if str(uri.path[-1]).startswith(';'):
                    yield event
                    continue
                # Fix link
                uri = uri.resolve2(';download')
                attributes = attributes.copy()
                attributes[(None, 'src')] = str(uri)
                yield START_ELEMENT, (tag_uri, tag_name, attributes), line

        languages = self.get_site_root().get_property('website_languages')
        for language in languages:
            handler = self.get_handler(language=language)
            events = list(fix_links(handler.events))
            handler.set_changed()
            handler.events = events



###########################################################################
# Register
###########################################################################
register_resource_class(WebPage)
register_resource_class(WebPage, format='application/xhtml+xml')
