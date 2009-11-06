# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
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
from datetime import datetime, timedelta
from os.path import basename

# Import from itools
from itools.core import thingy_lazy_property
from itools.csv import Property
from itools.datatypes import Integer
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype, guess_encoding
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.uri import get_reference
from itools.web import BaseView, STLView, ERROR, ViewField

# Import from ikaaro
from datatypes import ImageWidth
from forms import FileField, ReplaceFileField
import messages
from multilingual import Multilingual
from registry import get_resource_class
from resource_views import DBResource_Edit
from views_new import NewInstance


class File_NewInstance(NewInstance):

    view_title = MSG(u'Upload File')
    submit_value = MSG(u'Upload')


    name = None
    file = FileField(required=True, size=35, title=MSG(u'File'))


    @thingy_lazy_property
    def new_resource_name(self):
        # If the name is not explicitly given, use the title
        # or get it from the file
        name = self.name.value
        if name:
            return name

        title = self.title.value.strip()
        if title:
            return title

        filename, mimetype, body = self.file.value
        name, type, language = FileName.decode(filename)
        return name


    def action(self):
        filename, mimetype, body = self.file.value
        kk, type, language = FileName.decode(filename)

        # Web Pages are first class citizens
        if mimetype == 'text/html':
            body = stream_to_str_as_xhtml(HTMLParser(body))
            class_id = 'webpage'
        elif mimetype == 'application/xhtml+xml':
            class_id = 'webpage'
        else:
            class_id = mimetype
        cls = get_resource_class(class_id)

        # Multilingual resources, find out the language
        resource = self.resource
        context = self.context
        if issubclass(cls, Multilingual):
            if language is None:
                encoding = guess_encoding(body)
                text = cls.class_handler(string=body).to_text()
                language = guess_language(text)
                if language is None:
                    language = self.content_language

        # Build the resource
        name = self.new_resource_name
        kw = {'format': class_id, 'filename': filename}
        if issubclass(cls, Multilingual):
            kw['language'] = language
        else:
            kw['extension'] = type
        child = resource.make_resource(name, cls, body=body, **kw)

        # The title
        title = self.title.value.strip()
        title = Property(title, lang=self.content_language)
        child.metadata.set_property('title', title)

        # Ok
        context.message = messages.MSG_NEW_RESOURCE
        location = str(child.path)
        context.created(location)



class File_Download(BaseView):

    access = 'is_allowed_to_view'
    view_title = MSG(u"Download")


    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def http_get(self):
        context = self.context
        resource = self.resource

        # Content-Type
        content_type = resource.get_content_type()
        # Content-Disposition
        disposition = 'inline'
        if content_type.startswith('application/vnd.oasis.opendocument.'):
            disposition = 'attachment'
        filename = resource.get_property('filename')
        context.set_content_disposition(disposition, filename)
        # Ok
        body = resource.handler.to_str()
        context.ok(content_type, body)



class File_View(STLView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Download')
    icon = 'view.png'
    template = 'file/download_form.xml'


    def url(self):
        return '../' + self.resource.get_name()


    def filename(self):
        resource = self.resource
        filename = resource.get_property('filename')
        return filename if filename else resource.get_title()



class File_Edit(DBResource_Edit):

    file = ReplaceFileField()


    def get_value(self, name):
        if name == 'file':
            return None
        return super(File_Edit, self).get_value(name)


    def set_value(self, resource, context, name, value):
        if name != 'file':
            return DBResource_Edit.set_value(self, resource, context, name,
                                             value)

        # File
        filename, mimetype, body = value

        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
        handler_class = get_handler_class_by_mimetype(mimetype)
        if not isinstance(handler, handler_class):
            message = ERROR(u'Unexpected file of mimetype {type}',
                            type=mimetype)
            context.message = message
            return

        # Replace
        try:
            handler.load_state_from_string(body)
        except Exception, e:
            handler.load_state()
            message = ERROR(u'Failed to load the file: {error}', error=str(e))
            context.message = message
            return

        # Update "filename" property
        resource.set_property("filename", filename)
        # Update metadata format
        metadata = resource.metadata
        if '/' in metadata.format:
            if mimetype != metadata.format:
                metadata.format = mimetype

        # Update handler name
        handler_name = basename(handler.key)
        old_name, old_extension, old_lang = FileName.decode(handler_name)
        new_name, new_extension, new_lang = FileName.decode(filename)
        # FIXME Should 'FileName.decode' return lowercase extensions?
        new_extension = new_extension.lower()
        if old_extension != new_extension:
            # "handler.png" -> "handler.jpg"
            folder = resource.get_parent().handler
            filename = FileName.encode((old_name, new_extension, old_lang))
            folder.move_handler(handler_name, filename)



class File_ExternalEdit_View(STLView):

    access = 'is_allowed_to_edit'
    template = 'file/externaledit.xml'
    view_title = MSG(u'External Editor')
    icon = 'external.png'
    encodings = None



class File_ExternalEdit(BaseView):

    access = 'is_allowed_to_edit'


    def http_get(self):
        encoding = context.get_form_value('encoding')

        uri = get_reference(context.uri)
        handler = resource.handler
        title = resource.get_property('title')
        if title:
            title = title.encode(encoding or 'UTF-8')
        else:
            title = resource.get_name()

        soup_message = context.soup_message
        lines = [
            'url:%s://%s%s' % (uri.scheme, uri.authority, uri.path[:-1]),
            'meta_type:toto', # FIXME Check if zopeedit really needs this
            'content_type:%s' % handler.get_mimetype(),
            'cookie:%s' % soup_message.get_header('Cookie'),
            'title:%s' % title]

        if resource.is_locked():
            username, timestamp, key = resource.get_lock()
            # locks expire after 1 hour
            if timestamp + timedelta(hours=1) < datetime.now():
                resource.unlock()
                context.commit = True
            else:
                # always borrow lock from same user
                if username == context.user.get_name():
                    lines.append('lock-token:%s' % lock.lock_key)
                    lines.append('borrow_lock:1')
                else:
                    message = ERROR(u'This page is locked by another user')
                    return context.come_back(message, goto='.')

        auth = context.get_header('Authorization')
        if auth:
            lines.append('auth:%s' % auth)

        lines.append('')

        # TODO known bug from ExternalEditor requires rfc1123_date()
        # Using RESPONSE.setHeader('Pragma', 'no-cache') would be better, but
        # this chokes crappy most MSIE versions when downloads happen on SSL.
        # cf. http://support.microsoft.com/support/kb/articles/q316/4/31.asp
        #context.set_header('Last-Modified', rfc1123_date())
        context.set_header('Pragma', 'no-cache')

        # Encoding
        if encoding is None:
            lines.append(handler.to_str())
        else:
            lines.append(handler.to_str(encoding))

        context.ok('application/x-zope-edit', '\n'.join(lines))



class Image_Thumbnail(BaseView):

    access = 'is_allowed_to_view'

    width = ViewField(source='query', datatype=Integer(default=48))
    height = ViewField(source='query', datatype=Integer(default=48))


    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def http_get(self):
        context = self.context
        resource = self.resource

        width = self.width.value
        height = self.height.value

        # TODO generate the thumbnail in the resource format
        format = 'png' if resource.metadata.format == 'image/png' else 'jpeg'
        data, format = resource.handler.get_thumbnail(width, height, format)
        if data is None:
            default = context.get_template('icons/48x48/image.png')
            data = default.to_str()
            format = 'png'

        # Filename
        filename = resource.get_value('filename')
        if filename:
            context.set_content_disposition('inline', filename)

        # Ok
        context.ok('image/%s' % format, data)



class Image_View(STLView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'View')
    template = 'binary/Image_view.xml'
    styles = ['/ui/gallery/style.css']
    scripts = ['/ui/gallery/javascript.js']

    width = ViewField(source='query', datatype=Integer(default=800))
    height = ViewField(source='query', datatype=Integer(default=600))


    @thingy_lazy_property
    def images(self):
        from file import Image

        user = self.context.user
        parent = self.resource.get_parent()
        ac = parent.get_access_control()

        return [ x for x in parent.search_resources(cls=Image)
                 if ac.is_allowed_to_view(user, x) ]


    @thingy_lazy_property
    def my_index(self):
        for index, image in enumerate(self.images):
            if image is self.resource:
                return index
        return None


    @thingy_lazy_property
    def image(self):
        width, height = self.resource.handler.get_size()
        return {'width': width, 'height': height}


    def image_link(self):
        return self.resource.path


    def image_view(self):
        return self.preload[0]


    def widths(self):
        return ImageWidth.get_namespace(self.width.value)


    @thingy_lazy_property
    def prev_image(self):
        my_index = self.my_index
        return self.images[my_index - 1] if (my_index > 0) else None


    def prev_link(self):
        prev_image = self.prev_image
        return prev_image.path if prev_image else None


    @thingy_lazy_property
    def next_image(self):
        images = self.images
        my_index = self.my_index
        return images[my_index + 1] if my_index + 1 < len(images) else None


    def next_link(self):
        next_image = self.next_image
        return next_image.path if next_image else None


    @thingy_lazy_property
    def preload(self):
        width = self.width.value
        height = self.height.value

        images = self.images
        my_index = self.my_index

        # List of 5 next and previous images to preload
        next_images = images[my_index + 2:my_index + 6]
        min_index = my_index - 5 if my_index > 5 else 0
        max_index = my_index - 1 if my_index > 1 else 0
        previous_images = images[min_index:max_index]
        previous_images.reverse()
        preload = []
        for image in ([self.resource, self.next_image, self.prev_image]
                      + next_images + previous_images):
            if image is None:
                continue
            prefix = get_reference(image.path)
            # Preload with same size preferences than the current one
            if width and height:
                # Preload a thumbnail
                uri = prefix.resolve_name(';thumb').replace(width=width,
                                                            height=height)
            else:
                # Preload the full size
                uri = prefix.resolve_name(';download')
            preload.append(str(uri))

        return preload


    def preload_array(self):
        array = [ ('"%s"' % x) for x in self.preload ]
        return ', '.join(array)



# FIXME This is broken, check http://alistapart.com/articles/byebyeembed
class Video_View(STLView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'View')
    template = '/ui/binary/Video_view.xml'


    def get_namespace(self, resource, context):
        return {'format': resource.handler.get_mimetype()}



class Archive_View(File_View):

    access = 'is_allowed_to_view'
    view_title = MSG(u'View')
    template = '/ui/binary/Archive_view.xml'

    def get_namespace(self, resource, context):
        namespace = File_View.get_namespace(self, resource, context)
        contents = resource.handler.get_contents()
        namespace['contents'] = '\n'.join(contents)
        return namespace



class Flash_View(File_View):

    access = 'is_allowed_to_view'
    view_title = MSG(u'View')
    template = '/ui/binary/Flash_view.xml'

