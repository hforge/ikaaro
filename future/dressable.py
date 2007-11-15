# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
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
import mimetypes
from HTMLParser import HTMLParseError

# Import from itools
from itools.datatypes import is_datatype, DateTime
from itools.uri import Path
from itools.stl import stl, set_prefix
from itools.xhtml import Document
from itools.xml import Parser
from itools.handlers import Image
from itools.rest import checkid
from itools.web import get_context
from itools.html import Parser as HTMLParser

# Import from ikaaro
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.folder import Folder
from ikaaro.file import File
from ikaaro.html import XHTMLFile, EpozEditable
from ikaaro.messages import *



class Dressable(Folder, EpozEditable):
    """
    A Dressable object is a folder with a specific view which is defined
    by the schema. In addition of the schema, it is necessary to redefine
    the variable __fixed_handlers__.
    """

    class_id = 'dressable'
    class_title = u'Dressable'
    class_description = u'A dressable folder'
    class_views = ([['view'], ['edit_document']] + Folder.class_views)
    __fixed_handlers__ = ['index.xhtml']
    template = '/ui/future/dressable_view.xml'
    schema = {'content': ('index.xhtml', XHTMLFile),
              'browse_folder': 'browse_folder',
              'browse_file': 'browse_file'}

    browse_template = list(Parser("""
<stl:block xmlns="http://www.w3.org/1999/xhtml"
  xmlns:stl="http://xml.itools.org/namespaces/stl">
  <h2>${title}</h2>
  <ul id="${id}">
    <li stl:repeat="handler handlers">
      <img src="${handler/icon}" />
      <a href="${handler/path}">${handler/label}</a>
    </li>
  </ul>
</stl:block>
    """))


    def new(self, **kw):
        Folder.new(self, **kw)
        cache = self.cache

        for key, data in self.schema.iteritems():
            if isinstance(data, tuple):
                name, cls = data
                if is_datatype(cls, Document):
                    handler = cls()
                    cache[name] = handler
                    cache['%s.metadata' % name] = handler.build_metadata()


    def get_document_types(self):
        return Folder.get_document_types(self) + [Dressable]


    def GET(self, context):
        return context.uri.resolve2(';view')


    #######################################################################
    # API / Private
    #######################################################################
    def _get_image(self, context, handler):
        here = context.handler
        path = here.get_pathto(handler)
        content = '<img src="%s"/>' % path
        return Parser(content)


    def _get_document(self, context, handler):
        here = context.handler
        stream = handler.get_body().get_content_elements()
        prefix = here.get_pathto(handler)
        return set_prefix(stream, prefix)


    def _get_schema_handler_names(self):
        handlers = []
        for key, data in self.schema.iteritems():
            if isinstance(data, tuple):
                name, kk = data
                handlers.append(name)
        return handlers


    def _get_handler_label(self, name):
        if self.has_handler(name):
            handler = self.get_handler(name)
            label = handler.get_property('dc:title')
            if label:
                return label

        for key, data in self.schema.iteritems():
            if isinstance(data, tuple):
                handler_name, kk = data
                if handler_name == name:
                    return unicode(key)
        return None


    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    def view(self, context):
        namespace = {}

        for key, data in self.schema.iteritems():
            content = ''
            if isinstance(data, tuple):
                name, kk = data
                if self.has_handler(name):
                    handler = self.get_handler(name)
                    if is_datatype(handler, Image):
                        content = self._get_image(context, handler)
                    elif is_datatype(handler, Document):
                        content = self._get_document(context, handler)
                    else:
                        raise NotImplementedError
            else:
                content = getattr(self, data)(context)
            namespace[key] = content

        context.styles.append('/ui/future/dressable.css')

        handler = self.get_handler(self.template)
        return stl(handler, namespace)


    def get_views(self):
        views = Folder.get_views(self)
        views = list(views)
        try:
            edit_index = views.index('edit_document')
            first_edit_subview = self.get_first_edit_subview()
            if first_edit_subview is not None:
                views[edit_index] = first_edit_subview
            else:
                views.pop(edit_index)
        except ValueError: # FO
            pass
        return views


    #######################################################################
    # API
    #######################################################################
    edit_document__access__ = 'is_allowed_to_edit'
    edit_document__label__ = 'edit'
    def edit_document(self, context):
        name = context.get_form_value('dress_name')
        if context.get_form_value('external'):
            return context.uri.resolve('%s/;externaledit' % name)
        handler = self.get_handler(name)
        return XHTMLFile.edit_form(handler, context)


    edit_image__access__ = 'is_allowed_to_edit'
    def edit_image(self, context):
        name = context.get_form_value('name')
        if self.has_handler(name) is False:
            return context.uri.resolve2('../;add_image_form?name=%s' % name)

        namespace = {}
        name = context.get_form_value('name')
        namespace['name'] = name
        namespace['class_id'] = self.get_class_id_image(name)
        message = self.gettext(MSG_DELETE_OBJECT)
        msg = 'return confirmation("%s");' % message.encode('utf_8')
        namespace['remove_action'] = msg

        # size
        handler = self.get_handler(name)
        size = handler.get_size()
        if size is not None:
            width, height = size
            ratio = width / float(height)
            if ratio > 1:
                if width > 640:
                    height = height * 640.0 / width
                    width = 640
            else:
                if height > 480:
                    width = width * 480.0 / height
                    height = 480
        else:
            width, height = (None, None)
        namespace['width'] = width
        namespace['height'] = height

        handler = self.get_object('/ui/future/dressable_edit_image.xml')
        return stl(handler, namespace)


    #######################################################################
    # Edit / Inline / edit
    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context, sanitize=False):
        # FIXME Duplicated code (cms.html)
        dress_name = context.get_form_value('dress_name')
        dress_handler = self.get_handler(dress_name)
        timestamp = context.get_form_value('timestamp', type=DateTime)
        # Compare the dressable's timestamp and not the folder's timestamp
        if timestamp is None or timestamp < dress_handler.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        new_body = context.get_form_value('data')
        try:
            new_body = HTMLParser(new_body)
        except HTMLParseError:
            return context.come_back(u'Invalid HTML code.')
        if sanitize:
            new_body = sanitize_stream(new_body)
        # Save the changes
        # "get_epoz_document" is to set in your editable handler
        document = self.get_epoz_document()
        old_body = document.get_body()
        document.set_changed()
        document.events = (document.events[:old_body.start+1]
                           + new_body
                           + document.events[old_body.end:])

        return context.come_back(MSG_CHANGES_SAVED)


    def get_class_id_image(self, handler_name):
        """
        Return the class id of a handler
        """
        for key, data in self.schema.iteritems():
            if isinstance(data, tuple):
                name, cls = data
                if name == handler_name:
                    return cls.class_id
        raise AttributeError


    add_image_form__access__ = 'is_allowed_to_edit'
    def add_image_form(self, context):
        namespace = {}
        name = context.get_form_value('name')
        namespace['name'] = name
        namespace['class_id'] = self.get_class_id_image(name)

        handler = self.get_object('/ui/future/dressable_add_image.xml')
        return stl(handler, namespace)


    new_image_resource__access__ = 'is_allowed_to_edit'
    def new_image_resource(self, context):
        class_id = context.get_form_value('class_id')
        image_name = context.get_form_value('name')

        # Check input data
        file = context.get_form_value('file')
        if file is None:
            return context.come_back(MSG_EMPTY_FILENAME)

        # Interpret input data (the mimetype sent by the browser can be
        # minimalistic)
        kk, mimetype, body = file
        guessed, encoding = mimetypes.guess_type(image_name)

        # Check the name
        name = checkid(image_name)
        if name is None:
            return context.come_back(MSG_BAD_NAME)

        # Add the language extension to the name
        if mimetype.startswith('image/') is False:
            return context.come_back(u'The file is not an image')

        # Build the object
        cls = get_object_class(class_id)
        handler = cls(string=body)
        metadata = handler.build_metadata()
        # Add the object
        if self.has_handler(image_name):
            handler = self.get_handler(image_name)
            handler.load_state_from_string(body)
        else:
            handler, metadata = self.set_object(name, handler, metadata)

        goto = './;view'
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)


    remove_image__access__ = 'is_allowed_to_edit'
    def remove_image(self, context):
        name = context.get_form_value('name')
        self.del_object(name)
        goto = './;view'
        return context.come_back(u'Objects removed: %s' % name, goto=goto)


    def get_epoz_document(self):
        name = get_context().get_form_value('dress_name')
        return self.get_handler(name)


    def get_browse(self, context, cls, exclude=[]):
        namespace = {}
        here = context.handler
        folders = []
        handlers = self.search_handlers(handler_class=cls)
        # Check access rights
        user = context.user

        for handler in handlers:
            if handler.name in exclude:
                continue
            ac = handler.get_access_control()
            if ac.is_allowed_to_view(user, handler):
                d = {}
                label = handler.get_property('dc:title')
                if label is None or label == '':
                    label = handler.name
                path_to_icon = handler.get_path_to_icon()
                if path_to_icon.startswith(';'):
                    path_to_icon = Path('%s/' % handler.name)
                    path_to_icon = path_to_icon.resolve(path_to_icon)
                d['label'] = label
                d['icon'] = path_to_icon
                d['path'] = here.get_pathto(handler)
                folders.append((label, d))

        folders.sort()
        return [folder for kk, folder in folders]


    def browse_folder(self, context):
        namespace = {}
        namespace['id'] = 'browse_folder'
        namespace['title'] = 'Folders'
        namespace['handlers'] = self.get_browse(context, Folder)
        return stl(events=self.browse_template, namespace=namespace)


    def browse_file(self, context):
        exclude = self._get_schema_handler_names()
        namespace = {}
        namespace['id'] = 'browse_file'
        namespace['title'] = 'Files'
        namespace['handlers'] = self.get_browse(context, File, exclude=exclude)
        return stl(events=self.browse_template, namespace=namespace)


    #######################################################################
    # User interface
    #######################################################################
    def get_subviews(self, name):
        if name.split('?')[0] == 'edit_document':
            subviews = []
            for key, data in self.schema.iteritems():
                if isinstance(data, tuple):
                    name, cls = data
                    if is_datatype(cls, Document):
                        ref = 'edit_document?dress_name=%s' % name
                        subviews.append(ref)
                        ref = 'edit_document?dress_name=%s&external=1' % name
                        subviews.append(ref)
                    elif is_datatype(cls, Image):
                        ref = 'edit_image?name=%s' % name
                        subviews.append(ref)
            subviews.sort()
            return subviews

        return Folder.get_subviews(self, name)


    def get_first_edit_subview(self):
        for key, data in self.schema.iteritems():
            if isinstance(data, tuple):
                name, cls = data
                if is_datatype(cls, Document):
                    return 'edit_document?dress_name=%s' % name
                elif is_datatype(cls, Image):
                    return 'edit_image?name=%s' % name
        return None


    def edit_document__sublabel__(self, **kw):
        dress_name = kw.get('dress_name')
        label = self._get_handler_label(dress_name)
        if kw.get('external'):
            label = u'%s (External)' % label
        return label


    def edit_image__sublabel__(self, **kw):
        name = kw.get('name')
        return self._get_handler_label(name)



register_object_class(Dressable)
