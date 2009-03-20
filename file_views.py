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

# Import from itools
from itools.datatypes import Integer, Unicode
from itools.gettext import MSG
from itools.handlers import get_handler_class_by_mimetype, guess_encoding
from itools.handlers import merge_dicts
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.uri import get_reference
from itools.vfs import FileName
from itools.web import BaseView, STLView, STLForm, INFO, ERROR
from itools.xapian import PhraseQuery

# Import from ikaaro
from datatypes import FileDataType, ImageWidth
from folder_views import Folder_BrowseContent
from forms import title_widget, file_widget, description_widget
from forms import subject_widget
import messages
from multilingual import Multilingual
from registry import get_resource_class
from resource_views import AddResourceMenu, DBResource_Edit
from views import NewInstanceForm


class File_NewInstance(NewInstanceForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Upload File')
    template = '/ui/file/new_instance.xml'
    schema = {
        'title': Unicode,
        'file': FileDataType(mandatory=True),
    }
    context_menus = [AddResourceMenu()]


    def get_namespace(self, resource, context):
        type = context.get_query_value('type')
        cls = get_resource_class(type)
        return {
            'class_id': cls.class_id,
            'class_title': cls.class_title,
            'title': context.get_form_value('title', type=Unicode),
        }


    def get_new_resource_name(self, form):
        filename, mimetype, body = form['file']
        name, type, language = FileName.decode(filename)

        return form['title'].strip() or name


    def action(self, resource, context, form):
        filename, mimetype, body = form['file']
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
        if issubclass(cls, Multilingual):
            if language is None:
                encoding = guess_encoding(body)
                text = cls.class_handler(string=body).to_text()
                language = guess_language(text)
                if language is None:
                    language = resource.get_content_language(context)

        # Build the resource
        name = form['name']
        kw = {'format': class_id, 'filename': filename}
        if issubclass(cls, Multilingual):
            kw['language'] = language
        else:
            kw['extension'] = type
        child = cls.make_resource(cls, resource, name, body, **kw)

        # The title
        title = form['title'].strip()
        language = resource.get_content_language(context)
        child.metadata.set_property('title', title, language=language)

        # Ok
        goto = './%s/' % name
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class File_Download(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u"Download")


    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        response = context.response
        # Filename
        filename = resource.get_property('filename')
        if filename is not None:
            response.set_header('Content-Disposition',
                                'inline; filename="%s"' % filename)
        # Content-Type
        response.set_header('Content-Type', resource.get_content_type())
        return resource.handler.to_str()



class File_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Download')
    icon = 'view.png'
    template = '/ui/file/download_form.xml'


    def get_namespace(self, resource, context):
        filename = resource.get_property('filename')
        if not filename:
            filename = resource.get_title()
        return {
            'url': '../' + resource.name,
            'filename': filename}



class File_Upload(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Replace')
    icon = 'upload.png'
    template = '/ui/file/upload.xml'
    schema = {
        'file': FileDataType(mandatory=True),
    }


    def action(self, resource, context, form, file='file'):
        file = form[file]
        # Added for views reusing this method but where the file is not
        # mandatory.
        if file is None:
            return

        filename, mimetype, body = file

        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
        handler_class = get_handler_class_by_mimetype(mimetype)
        if not isinstance(handler, handler_class):
            message = ERROR(u'Unexpected file of mimetype ${type}',
                            type=mimetype)
            context.message = message
            return

        # Replace
        try:
            handler.load_state_from_string(body)
        except Exception, e:
            handler.load_state()
            message = ERROR(u'Failed to load the file: ${error}',
                            error=str(e))
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
        handler_name = handler.uri.path.get_name()
        old_name, old_extension, old_lang = FileName.decode(handler_name)
        new_name, new_extension, new_lang = FileName.decode(filename)
        # FIXME Should 'FileName.decode' return lowercase extensions?
        new_extension = new_extension.lower()
        if old_extension != new_extension:
            # "handler.png" -> "handler.jpg"
            folder = resource.parent.handler
            filename = FileName.encode((old_name, new_extension, old_lang))
            folder.move_handler(handler_name, filename)

        # Ok
        context.server.change_resource(resource)
        context.message = INFO(u'Version uploaded')



class File_Edit(DBResource_Edit, File_Upload):
    schema = merge_dicts(DBResource_Edit.schema, file=FileDataType)
    widgets = [title_widget, file_widget, description_widget, subject_widget]


    def get_value(self, resource, context, name, datatype):
        if name == 'file':
            return None
        return DBResource_Edit.get_value(self, resource, context, name,
                                         datatype)


    def action(self, resource, context, form):
        DBResource_Edit.action(self, resource, context, form)
        File_Upload.action(self, resource, context, form)




class File_ExternalEdit(BaseView):

    access = 'is_allowed_to_edit'


    def GET(self, resource, context):
        # Get the request and response
        request, response = context.request, context.response

        encoding = context.get_form_value('encoding')

        uri = context.uri
        uri_string = '%s://%s/%s' % (uri.scheme, uri.authority, uri.path[:-1])
        uri = get_reference(uri_string)
        handler = resource.handler
        title = resource.get_property('title')
        if title:
            title = title.encode(encoding or 'UTF-8')
        else:
            title = resource.name

        r = [
            'url:%s' % str(uri),
            'meta_type:toto', # FIXME Check if zopeedit really needs this
            'content_type:%s' % handler.get_mimetype(),
            'cookie:%s' % request.get_cookies_as_str(),
            'title:%s' % title,
            ]

        if resource.is_locked():
            lock = resource.get_lock()
            # locks expire after 1 hour
            if lock.lock_timestamp + timedelta(hours=1) < datetime.now():
                resource.unlock()
                context.commit = True
            else:
                # always borrow lock from same user
                if lock.username == context.user.name:
                    r.append('lock-token:%s' % lock.key)
                    r.append('borrow_lock:1')
                else:
                    message = ERROR(u'This page is locked by another user')
                    return context.come_back(message, goto='.')

        if request.has_header('Authorization'):
            r.append('auth:%s' % request.get_header('Authorization'))

        r.append('')

        # TODO known bug from ExternalEditor requires rfc1123_date()
        # Using RESPONSE.setHeader('Pragma', 'no-cache') would be better, but
        # this chokes crappy most MSIE versions when downloads happen on SSL.
        # cf. http://support.microsoft.com/support/kb/articles/q316/4/31.asp
        #response.set_header('Last-Modified', rfc1123_date())
        response.set_header('Pragma', 'no-cache')

        # Encoding
        if encoding is None:
            r.append(handler.to_str())
        else:
            r.append(handler.to_str(encoding))

        data = '\n'.join(r)

        response.set_header('Content-Type', 'application/x-zope-edit')
        return data



class File_Backlinks(Folder_BrowseContent):
    """Backlinks are the list of resources pointing to this resource.  This
    view answers the question "where is this resource used?" You'll see all
    WebPages and WikiPages (for example) referencing it.  If the list is
    empty, you can consider it is "orphan".
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Backlinks")
    icon = 'rename.png'

    search_template = None
    search_schema = {}

    # Skip AddResourceMenu
    context_menus = []

    def get_table_columns(self, resource, context):
        cols = Folder_BrowseContent.get_table_columns(self, resource, context)
        return [ col for col in cols if col[0] != 'checkbox' ]


    def get_items(self, resource, context):
        query = PhraseQuery('links', str(resource.get_abspath()))
        return context.root.search(query)


    table_actions = []



class Image_Thumbnail(BaseView):

    access = 'is_allowed_to_view'

    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        width = context.get_form_value('width', type=Integer, default=48)
        height = context.get_form_value('height', type=Integer, default=48)

        data, format = resource.handler.get_thumbnail(width, height)
        if data is None:
            default = resource.get_resource('/ui/icons/48x48/image.png')
            data = default.to_str()
            format = 'png'

        response = context.response
        # Filename
        filename = resource.get_property('filename')
        if filename is not None:
            response.set_header('Content-Disposition',
                                'inline; filename="%s"' % filename)
        # Content-Type
        response.set_header('Content-Type', 'image/%s' % format)
        return data



class Image_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Image_view.xml'
    # Image default size as a string (empty = full size)
    default_width = ''
    default_height = ''


    def get_browse_images(self, resource, context):
        from file import Image
        user = context.user
        parent = resource.parent
        ac = parent.get_access_control()

        return [ image for image in parent.search_resources(cls=Image)
                 if ac.is_allowed_to_view(user, image) ]


    def get_namespace(self, resource, context):
        context.styles.append('/ui/gallery/style.css')
        context.scripts.append('/ui/gallery/javascript.js')
        size = context.get_form_value('size', type=Integer)
        width = context.get_form_value('width', default=self.default_width)
        height = context.get_form_value('height', default=self.default_height)
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
            if image is None:
                continue
            prefix = get_reference(context.get_link(image))
            # Preload with same size preferences than the current one
            if width and height:
                # Preload a thumbnail
                uri = prefix.resolve2(';thumb').replace(width=width,
                                                        height=height)
            else:
                # Preload the full size
                uri = prefix.resolve2(';download')
            preload.append(str(uri))

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



class Archive_View(File_View):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Archive_view.xml'

    def get_namespace(self, resource, context):
        namespace = File_View.get_namespace(self, resource, context)
        contents = resource.handler.get_contents()
        namespace['contents'] = '\n'.join(contents)
        return namespace



class Flash_View(File_View):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Flash_view.xml'

