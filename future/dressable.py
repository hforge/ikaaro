# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
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

# Import from the Standard Library
from mimetypes import guess_type
from string import Template

# Import from itools
from itools.datatypes import is_datatype, DateTime, FileName
from itools.handlers import checkid
from itools.html import HTMLParser
from itools.stl import stl, set_prefix
from itools.uri import Path
from itools.web import get_context
from itools.xml import XMLParser, XMLError

# Import from ikaaro
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.folder import Folder
from ikaaro.file import File
from ikaaro.binary import Image
from ikaaro.html import WebPage, EpozEditable
from ikaaro.messages import *



class Dressable(Folder, EpozEditable):
    """A Dressable object is a folder with a specific view which is defined
    by the layout. In addition of the layout, it is necessary to redefine
    the variable __fixed_handlers__.
    """

    class_id = 'dressable'
    class_version = '20071215'
    class_title = u'Dressable'
    class_description = u'A dressable folder'
    class_views = ([['view'], ['edit_document']] + Folder.class_views)
    __fixed_handlers__ = ['index']
    template = '/ui/future/dressable_view.xml'
    layout = {'content': ('index', WebPage),
              'browse_folder': 'browse_folder',
              'browse_file': 'browse_file'}

    browse_template = list(XMLParser("""
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

    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        # populate the dressable
        cls._populate(cls, folder, name)


    @staticmethod
    def _populate(cls, folder, base_name):
        """Populate the dressable from the layout"""
        for key, data in cls.layout.iteritems():
            if isinstance(data, tuple):
                handler_name, handler_cls = data
                if issubclass(handler_cls, WebPage):
                    full_name = '%s/%s.metadata' % (base_name, handler_name)
                    metadata = handler_cls.build_metadata()
                    folder.set_handler(full_name, metadata)


    def get_document_types(self):
        return Folder.get_document_types(self) + [Dressable]


    def GET(self, context):
        return context.uri.resolve2(';view')


    #######################################################################
    # API / Private
    #######################################################################
    def _get_image(self, context, handler):
        here = context.object
        path = here.get_pathto(handler)
        content = '<img src="%s"/>' % path
        return XMLParser(content)


    def _get_document(self, context, handler):
        here = context.object
        body = handler.get_epoz_document().get_body()
        if body is None:
            return None
        stream = body.get_content_elements()
        prefix = here.get_pathto(handler)
        return set_prefix(stream, prefix)


    def _get_layout_handler_names(self):
        handlers = []
        for key, data in self.layout.iteritems():
            if isinstance(data, tuple):
                name, kk = data
                handlers.append(name)
        return handlers


    def _get_object_label(self, name):
        if self.has_object(name):
            object = self.get_object(name)
            label = object.get_property('title')
            if label:
                return label

        for key, data in self.layout.iteritems():
            if isinstance(data, tuple):
                handler_name, kk = data
                if handler_name == name:
                    return unicode(key)
        return None


    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    def view(self, context):
        namespace = {}

        for key, data in self.layout.iteritems():
            content = ''
            if isinstance(data, tuple):
                name, kk = data
                if self.has_object(name):
                    object = self.get_object(name)
                    if is_datatype(object, Image):
                        content = self._get_image(context, object)
                    elif is_datatype(object, WebPage):
                        content = self._get_document(context, object)
                    else:
                        raise NotImplementedError
            else:
                content = getattr(self, data)(context)
            namespace[key] = content

        context.styles.append('/ui/future/dressable.css')

        handler = self.get_object(self.template)
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
        object = self.get_object(name)
        cls = self.get_class(name)
        return cls.edit_form(object, context)


    edit_image__access__ = 'is_allowed_to_edit'
    edit_image__label__ = 'edit image'
    def edit_image(self, context):
        name = context.get_form_value('name')
        if self.has_object(name) is False:
            return context.uri.resolve2('../;add_image_form?name=%s' % name)

        namespace = {}
        name = context.get_form_value('name')
        namespace['name'] = name
        namespace['class_id'] = self.get_class(name).class_id
        message = self.gettext(MSG_DELETE_OBJECT)
        msg = 'return confirmation("%s");' % message.encode('utf_8')
        namespace['remove_action'] = msg

        # size
        object = self.get_object(name)
        size = object.handler.get_size()
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
        dress_object = self.get_object(dress_name)
        timestamp = context.get_form_value('timestamp', type=DateTime)
        # Compare the dressable's timestamp and not the folder's timestamp
        if timestamp is None:
            return context.come_back(MSG_EDIT_CONFLICT)
        document = self.get_epoz_document()
        if document.timestamp is not None and timestamp < document.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        # Sanitize
        new_body = context.get_form_value('data')
        try:
            new_body = HTMLParser(new_body)
        except XMLError:
            return context.come_back(u'Invalid HTML code.')
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


    def get_class(self, handler_name):
        """
        Return the class of a handler
        """
        for key, data in self.layout.iteritems():
            if isinstance(data, tuple):
                name, cls = data
                if name == handler_name:
                    return cls
        raise AttributeError


    add_image_form__access__ = 'is_allowed_to_edit'
    def add_image_form(self, context):
        namespace = {}
        name = context.get_form_value('name')
        namespace['name'] = name
        namespace['class_id'] = self.get_class(name).class_id

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
        guessed, encoding = guess_type(image_name)

        # Check the name
        name = checkid(image_name)
        if name is None:
            return context.come_back(MSG_BAD_NAME)

        # Check the mimetype
        if mimetype.startswith('image/') is False:
            return context.come_back(u'The file is not an image')

        # Add the language extension to the name
        cls = Image
        extension = cls.class_handler.class_extension
        name = FileName.encode((name, extension, None))

        if self.has_object(image_name):
            object = self.get_object(image_name)
            object.handler.load_state_from_string(body)
        else:
            # Build the object
            container = self
            object = cls.make_object(cls, container, name, body=body)
            # The metadata
            metadata = object.metadata
            language = container.get_content_language(context)
            metadata.set_property('title', name, language=language)

        goto = './;view'
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)


    remove_image__access__ = 'is_allowed_to_edit'
    def remove_image(self, context):
        name = context.get_form_value('name')
        self.del_object(name)
        goto = './;view'
        return context.come_back(MSG_OBJECTS_REMOVED, objects=name, goto=goto)


    def get_epoz_document(self):
        name = get_context().get_form_value('dress_name')
        return self.get_object(name).handler


    def get_browse(self, context, cls, exclude=[]):
        namespace = {}
        here = context.object
        folders = []
        handlers = self.search_objects(object_class=cls)
        # Check access rights
        user = context.user

        for handler in handlers:
            if handler.name in exclude:
                continue
            ac = handler.get_access_control()
            if ac.is_allowed_to_view(user, handler):
                d = {}
                label = handler.get_property('title')
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
        exclude = self._get_layout_handler_names()
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
            for key, data in self.layout.iteritems():
                if isinstance(data, tuple):
                    name, cls = data
                    if is_datatype(cls, WebPage):
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
        keys = self.layout.keys()
        keys.sort()
        for key in keys:
            data = self.layout[key]
            if isinstance(data, tuple):
                name, cls = data
                if is_datatype(cls, WebPage):
                    return 'edit_document?dress_name=%s' % name
                elif is_datatype(cls, Image):
                    return 'edit_image?name=%s' % name
        return None


    def edit_document__sublabel__(self, **kw):
        dress_name = kw.get('dress_name')
        label = self._get_object_label(dress_name)
        if kw.get('external'):
            label = Template(u'$label (External)').substitute(label=label)
        return label


    def edit_image__sublabel__(self, **kw):
        name = kw.get('name')
        return self._get_object_label(name)


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self):
        Folder.update_20071215(self)


register_object_class(Dressable)
