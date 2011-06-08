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
from itools.datatypes import Boolean, Enumerate, HTTPDate, Integer, String
from itools.datatypes import PathDataType
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype
from itools.web import BaseView, STLView, STLForm, ERROR
from itools.web import FormError

# Import from ikaaro
from autoform import FileWidget, PathSelectorWidget, ReadOnlyWidget
from autoform import file_widget, location_widget, timestamp_widget
from autoform import title_widget, description_widget, subject_widget
from autoform import ProgressBarWidget
from datatypes import FileDataType
from folder import Folder
from messages import MSG_NAME_CLASH
from messages import MSG_NEW_RESOURCE, MSG_UNEXPECTED_MIMETYPE
from resource_views import DBResource_Edit
from views_new import NewInstance
from workflow import StateEnumerate, state_widget


class File_NewInstance(NewInstance):

    title = MSG(u'Upload File')
    schema = merge_dicts(NewInstance.schema,
        file=FileDataType(mandatory=True))

    widgets = [
        ReadOnlyWidget('cls_description'),
        FileWidget('file', title=MSG(u'File'), size=35),
        title_widget,
        location_widget,
        ProgressBarWidget()]


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        # or get it from the file
        name = form['name']
        if name:
            return name
        filename, mimetype, body = form['file']
        name, type, language = FileName.decode(filename)

        return form['title'] or name


    def action(self, resource, context, form):
        # Get the container
        container = form['container']
        # Make the resource
        name = form['name']
        filename, mimetype, body = form['file']
        language = container.get_edit_languages(context)[0]
        child = container._make_file(name, filename, mimetype, body, language)
        # Set properties
        title = Property(form['title'], lang=language)
        child.metadata.set_property('title', title)
        # Ok
        goto = str(resource.get_pathto(child))
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
            # Check whether the uploaded file matches the handler
            handler = resource.handler
            metadata = resource.metadata
            if mimetype != metadata.format:
                cls = get_handler_class_by_mimetype(mimetype, soft=True)
                if cls is None or not isinstance(handler, cls):
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
            if '/' in metadata.format:
                if mimetype != metadata.format:
                    metadata.format = mimetype

            # Update handler name
            handler_name = basename(handler.key)
            old_name, old_extension, old_lang = FileName.decode(handler_name)
            new_name, new_extension, new_lang = FileName.decode(filename)
            # FIXME Should 'FileName.decode' return lowercase extensions?
            if new_extension is not None:
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




class File_ExternalEdit(BaseView):

    access = 'is_allowed_to_edit'


    def GET(self, resource, context):
        """Protocol used (with restedit.py):
        1- We add a header to the content of the file
        2- The header is separated from the rest of the file by a "\n\n".
        3- An entry in the header is:

           header-name:header-body\n

           The header-name does not contain ":" and the header-body does not
           contain "\n"
        4- Everything is sent in utf-8
        """
        uri = context.uri
        handler = resource.handler
        header = [
            'url:%s://%s%s' % (uri.scheme, uri.authority, uri.path[:-1]),
            'last-modified:%s' % HTTPDate.encode(resource.get_mtime()),
            'content_type:%s' % handler.get_mimetype(),
            'title:%s' % resource.get_title().encode('utf-8'),
            'include-Cookie:iauth="%s"' % context.get_cookie('iauth'),
            'include-X-User-Agent:%s' % context.get_header('User-Agent')]

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
        data = handler.to_str()

        # TODO known bug from ExternalEditor requires rfc1123_date()
        # Using RESPONSE.setHeader('Pragma', 'no-cache') would be better, but
        # this chokes crappy most MSIE versions when downloads happen on SSL.
        # cf. http://support.microsoft.com/support/kb/articles/q316/4/31.asp
        #context.set_header('Last-Modified', rfc1123_date())
        context.set_header('Pragma', 'no-cache')
        context.content_type = 'application/x-restedit'
        context.set_content_disposition('inline', '%s.restedit' %
                                        resource.name)
        return header + data



class Image_Thumbnail(BaseView):

    access = 'is_allowed_to_view'

    query_schema = {
        'width': Integer,
        'height': Integer,
        'fit': Boolean(default=False),
        'lossy': Boolean(default=False)}

    def get_mtime(self, resource):
        return resource.handler.get_mtime()


    def GET(self, resource, context):
        handler = resource.handler
        image_width, image_height = handler.get_size()
        fit = context.query['fit']
        lossy = context.query['lossy']
        width = context.query['width']
        height = context.query['height']
        # XXX Special case for backwards compatibility
        if width is None and height is None:
            width = height = 48
        width = width or image_width
        height = height or image_height

        format = 'jpeg' if lossy else None
        data, format = handler.get_thumbnail(width, height, format, fit)
        if data is None:
            default = context.get_template('/ui/icons/48x48/image.png')
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

    # Image default size as a string (empty = full size)
    query_schema = {
        'size': String(default='800x600')}

    sizes = [
        ('640x480', u"small"),
        ('800x600', u"medium"),
        ('1024x768', u"large"),
        ('1280x1024', u"huge"),
        ('original', u"original")]


    def get_namespace(self, resource, context):
        size = context.query['size']
        if not size:
            size = self.get_query_schema()['size'].default

        # Menu
        widths = [
            {'size': x, 'title': title, 'selected': x == size}
            for (x, title) in self.sizes ]

        # img
        if size == 'original':
            link = ';download'
        else:
            try:
                width, height = size.split('x')
            except ValueError:
                width = height = size
            link = ';thumb?width=%s&height=%s' % (width, height)

        # Real width and height (displayed for reference)
        image_width, image_height = resource.handler.get_size()
        return {'widths': widths,
                'link': link,
                'image_width': image_width,
                'image_height': image_height}



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

    schema = {'target': PathDataType, 'update': Boolean}

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


    def _get_form(self, resource, context):
        form = STLForm._get_form(self, resource, context)

        # Get the target resource
        target = form['target']
        target = resource.get_resource(target, soft=True)
        if target is None:
            raise FormError, ERROR(u'Target does not exist.')
        if isinstance(target, Folder) is False:
            raise FormError, ERROR(u'Target must be a folder.')

        return form


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
        try:
            target.extract_archive(handler, language, update=form['update'])
        except RuntimeError, message:
            context.commit = False
            context.message = MSG_NAME_CLASH
            return

        # Ok
        message = MSG(u'Files extracted')
        goto = context.get_link(target)
        return context.come_back(message, goto=goto)



class Flash_View(File_View):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Flash_view.xml'
