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
from os.path import basename, splitext

# Import from itools
from itools.core import merge_dicts
from itools.csv import Property
from itools.datatypes import Integer, Unicode, String, HTTPDate, PathDataType
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype
from itools.web import BaseView, STLView, STLForm, ERROR

# Import from ikaaro
from autoform import title_widget, description_widget, subject_widget
from autoform import file_widget, timestamp_widget
from autoform import FileWidget, PathSelectorWidget, TextWidget
from datatypes import FileDataType, ImageWidth
from messages import MSG_NEW_RESOURCE, MSG_UNEXPECTED_MIMETYPE
from resource_views import DBResource_Edit
from views_new import NewInstance
from workflow import StateEnumerate, state_widget


class File_NewInstance(NewInstance):

    title = MSG(u'Upload File')
    schema = {
        'title': Unicode,
        'name': String,
        'file': FileDataType(mandatory=True)}
    widgets = [
        title_widget,
        TextWidget('name', title=MSG(u'Name'), default=''),
        FileWidget('file', title=MSG(u'File'), size=35)]


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        # or get it from the file
        name = form['name']
        if name:
            return name
        filename, mimetype, body = form['file']
        name, type, language = FileName.decode(filename)

        return form['title'].strip() or name


    def action(self, resource, context, form):
        # Make the resource
        name = form['name']
        filename, mimetype, body = form['file']
        language = resource.get_edit_languages(context)[0]
        child = resource._make_file(name, filename, mimetype, body, language)

        # Set the title
        title = form['title'].strip()
        title = Property(title, lang=language)
        child.metadata.set_property('title', title)

        # Ok
        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class File_Download(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u"Download")


    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def get_content_type(self, resource, context):
        return resource.get_content_type()


    def get_filename(self, resource, context):
        return resource.get_property('filename')


    def get_bytes(self, resource, context):
        return resource.handler.to_str()


    def GET(self, resource, context):
        # Content-Type
        content_type = self.get_content_type(resource, context)
        context.set_content_type(content_type)
        # Content-Disposition
        disposition = 'inline'
        if content_type.startswith('application/vnd.oasis.opendocument.'):
            disposition = 'attachment'
        filename = self.get_filename(resource, context)
        context.set_content_disposition(disposition, filename)
        # Ok
        return self.get_bytes(resource, context)



class File_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Download')
    icon = 'view.png'
    template = '/ui/file/download_form.xml'


    def get_namespace(self, resource, context):
        filename = resource.get_property('filename') or resource.get_title()
        return {'filename': filename}



class File_Edit(DBResource_Edit):

    def _get_schema(self, resource, context):
        return merge_dicts(
            DBResource_Edit.schema,
            state=StateEnumerate(resource=resource, context=context),
            file=FileDataType)


    widgets = [
        timestamp_widget, title_widget, state_widget, file_widget,
        description_widget, subject_widget]


    def get_value(self, resource, context, name, datatype):
        if name == 'file':
            return None
        return DBResource_Edit.get_value(self, resource, context, name,
                                         datatype)


    def set_value(self, resource, context, name, form):
        if name == 'file':
            # Upload file
            file = form['file']
            if file is None:
                return False

            filename, mimetype, body = file
            # Check wether the handler is able to deal with the uploaded file
            handler = resource.handler
            handler_class = get_handler_class_by_mimetype(mimetype)
            if not isinstance(handler, handler_class):
                context.message = MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)
                return True

            # Replace
            try:
                handler.load_state_from_string(body)
            except Exception, e:
                handler.load_state()
                message = ERROR(u'Failed to load the file: {error}',
                                error=str(e))
                context.message = message
                return True

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
                folder = resource.parent.handler
                filename = FileName.encode((old_name, new_extension, old_lang))
                folder.move_handler(handler_name, filename)

            return False
        return DBResource_Edit.set_value(self, resource, context, name, form)



class File_ExternalEdit_View(STLView):
    access = 'is_allowed_to_edit'
    template = '/ui/file/externaledit.xml'
    title = MSG(u'External Editor')
    icon = 'external.png'
    encodings = None


    def get_namespace(self, resource, context):
        return {'encodings': self.encodings}



class File_ExternalEdit(BaseView):

    access = 'is_allowed_to_edit'


    def GET(self, resource, context):
        """Protocol used (with restedit.py):
        1- we add a header to the content of the file.
        2- the header is separated from the rest of the file by a "\n\n".
        3- an entry in the header is:

           header-name:header-body\n

           The header-name does not contain ":" and the header-body does not
           contain "\n"
        """
        encoding = context.get_form_value('encoding')

        uri = context.uri
        handler = resource.handler
        title = resource.get_property('title')
        if title:
            title = title.encode(encoding or 'UTF-8')
        else:
            title = resource.name

        soup_message = context.soup_message
        header = [
            'url:%s://%s%s' % (uri.scheme, uri.authority, uri.path[:-1]),
            'last-modified:%s' % HTTPDate.encode(resource.get_mtime()),
            'content_type:%s' % handler.get_mimetype(),
            'cookie:%s' % soup_message.get_header('Cookie'),
            'title:%s' % title]

        # Try to guess the extension (optional)
        filename = resource.get_property('filename')
        if filename:
            extension = splitext(filename)[1]
            if extension:
                extension = extension[1:]
                if extension in resource.get_all_extensions():
                    # All OK
                    header.append('extension:.%s' % extension)

        # Authorization part
        auth = context.get_header('Authorization')
        if auth:
            header.append('auth:%s' % auth)

        # Add the "\n\n" and make the header
        header.append('\n')
        header = '\n'.join(header)

        # TODO known bug from ExternalEditor requires rfc1123_date()
        # Using RESPONSE.setHeader('Pragma', 'no-cache') would be better, but
        # this chokes crappy most MSIE versions when downloads happen on SSL.
        # cf. http://support.microsoft.com/support/kb/articles/q316/4/31.asp
        #context.set_header('Last-Modified', rfc1123_date())
        context.set_header('Pragma', 'no-cache')

        # Encoding
        if encoding is None:
            data = handler.to_str()
        else:
            data = handler.to_str(encoding)

        context.content_type = 'application/x-restedit'
        context.set_content_disposition('inline', '%s.restedit' %
                                        resource.name)
        return header + data



class Image_Thumbnail(BaseView):

    access = 'is_allowed_to_view'

    query_schema = {
        'width': Integer,
        'height': Integer}

    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def GET(self, resource, context):
        image_width, image_height = resource.handler.get_size()
        width = context.query['width'] or image_width
        height = context.query['height'] or image_height

        # TODO generate the thumbnail in the resource format
        format = 'png' if resource.metadata.format == 'image/png' else 'jpeg'
        data, format = resource.handler.get_thumbnail(width, height, format)
        if data is None:
            default = resource.get_resource('/ui/icons/48x48/image.png')
            data = default.to_str()
            format = 'png'

        # Headers
        context.set_content_type('image/%s' % format)
        filename = resource.get_property('filename')
        if filename:
            context.set_content_disposition('inline', filename)

        # Ok
        return data



class Image_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Image_view.xml'
    styles = ['/ui/gallery/style.css']
    scripts = ['/ui/gallery/javascript.js']

    # Image default size as a string (empty = full size)
    query_schema = {
        'width': String(default='800'),
        'height': String(default='600')}


    def get_browse_images(self, resource, context):
        from file import Image
        user = context.user
        parent = resource.parent
        ac = parent.get_access_control()

        return [ image for image in parent.search_resources(cls=Image)
                 if ac.is_allowed_to_view(user, image) ]


    def get_namespace(self, resource, context):
        size = context.get_form_value('size', type=Integer)
        width = context.query['width']
        height = context.query['height']
        images = self.get_browse_images(resource, context)

        my_index = None
        for index, image in enumerate(images):
            if image == resource:
                my_index = index
                break

        # Navigate to next image
        next_image = None
        next_link = None
        if my_index + 1 < len(images):
            next_image = images[my_index + 1]
            next_link = context.get_link(next_image)

        # Navigate to previous image
        prev_image = None
        prev_link = None
        if my_index > 0:
            prev_image = images[my_index - 1]
            prev_link = context.get_link(prev_image)

        # List of 5 next and previous images to preload
        next_images = images[my_index + 2:my_index + 6]
        min_index = my_index - 5 if my_index > 5 else 0
        max_index = my_index - 1 if my_index > 1 else 0
        previous_images = images[min_index:max_index]
        previous_images.reverse()
        preload = []
        for image in ([resource, next_image, prev_image]
                      + next_images + previous_images):
            if image:
                uri = '%s/;thumb?width=%s&height=%s'
                uri = uri % (context.get_link(image), width, height)
                preload.append(uri)

        # Real width and height (displayed for reference)
        image_width, image_height = resource.handler.get_size()

        return {'parent_link': context.get_link(resource.parent),
                'size': size,
                'width': width,
                'height': height,
                'preload': '"' + '", "'.join(preload) + '"',
                'prev_link': prev_link,
                'next_link': next_link,
                'widths': ImageWidth.get_namespace(width),
                'image_width': image_width,
                'image_height': image_height,
                'image_link': context.get_link(resource),
                'index': my_index + 1,
                'total': len(images),
                'image_view': preload[0]}



# FIXME This is broken, check http://alistapart.com/articles/byebyeembed
class Video_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Video_view.xml'


    def get_namespace(self, resource, context):
        return {'format': resource.handler.get_mimetype()}



class Archive_View(STLForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Archive_view.xml'

    schema = {'target': PathDataType}

    def get_namespace(self, resource, context):
        filename = resource.get_property('filename') or resource.get_title()
        contents = resource.handler.get_contents()
        contents = '\n'.join(contents)
        # Extract archive
        ac = resource.get_access_control()
        extract = ac.is_allowed_to_edit(context.user, resource)
        if extract:
            widget = PathSelectorWidget('target', value='..').render()
        else:
            widget = None
        # Ok
        return {'filename': filename, 'contents': contents,
                'extract': extract, 'widget': widget}


    def action(self, resource, context, form):
        # Get the list of paths to extract
        handler = resource.handler
        paths = handler.get_contents()
        paths.sort()

        # Get the target resource
        target = form['target']
        target = resource.get_resource(target)

        # Make the resources
        language = resource.get_edit_languages(context)[0]
        target.extract_archive(handler, language)

        # Ok
        message = MSG(u'Files extracted')
        goto = context.get_link(target)
        return context.come_back(message, goto=goto)


class Flash_View(File_View):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Flash_view.xml'
