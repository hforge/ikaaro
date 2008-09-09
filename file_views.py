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
from itools.handlers import guess_encoding, checkid
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.uri import get_reference
from itools.vfs import FileName
from itools.web import BaseView, STLView, STLForm
from itools.xapian import EqQuery

# Import from ikaaro
from datatypes import FileDataType
from folder_views import FolderBrowseContent
from messages import MSG_BAD_NAME, MSG_NAME_CLASH, MSG_NEW_RESOURCE
from multilingual import Multilingual
from registry import get_object_class
from resource_views import AddResourceMenu
from views import NewInstanceForm


class FileNewInstance(NewInstanceForm):

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
        cls = get_object_class(type)
        return {
            'class_id': cls.class_id,
            'title': context.get_form_value('title', type=Unicode),
        }


    def action(self, resource, context, form):
        filename, mimetype, body = form['file']
        title = form['title']

        # Check the filename is good
        name = title.strip() or filename
        name = checkid(name)
        if name is None:
            context.message = MSG_BAD_NAME
            return

        # Web Pages are first class citizens
        if mimetype == 'text/html':
            body = stream_to_str_as_xhtml(HTMLParser(body))
            class_id = 'webpage'
        elif mimetype == 'application/xhtml+xml':
            class_id = 'webpage'
        else:
            class_id = mimetype
        cls = get_object_class(class_id)

        # Multilingual objects, find out the language
        name, type, language = FileName.decode(name)
        if issubclass(cls, Multilingual):
            if language is None:
                encoding = guess_encoding(body)
                text = cls.class_handler(string=body).to_text()
                language = guess_language(text)
                if language is None:
                    language = resource.get_content_language(context)

        # Check the name is free
        if resource.has_resource(name):
            context.message = MSG_NAME_CLASH
            return

        # Build the object
        kw = {'format': class_id, 'filename': filename}
        if issubclass(cls, Multilingual):
            kw['language'] = language
        else:
            kw['extension'] = type
        object = cls.make_object(cls, resource, name, body, **kw)
        # The title
        language = resource.get_content_language(context)
        object.metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class FileDownload(BaseView):

    access = 'is_allowed_to_view'


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



class FileView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Download')
    icon = 'view.png'
    template = '/ui/file/download_form.xml'


    def get_namespace(self, resource, context):
        return {
            'url': '../' + resource.name,
            'title_or_name': resource.get_title(),
        }



class FileUpload(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Replace')
    icon = 'button_upload.png'
    template = '/ui/file/upload.xml'
    schema = {
        'file': FileDataType(mandatory=True),
    }


    def action(self, resource, context, form):
        file = form['file']
        filename, mimetype, body = file

        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
        if mimetype != handler.get_mimetype():
            message = MSG(u'Unexpected file of mimetype ${type}')
            context.message = message.gettext(type=mimetype)
            return

        # Replace
        try:
            handler.load_state_from_string(body)
        except:
            handler.load_state()
            message = MSG(u'Failed to load the file, may contain errors.')
            context.message = message
            return

        # Ok
        context.server.change_object(resource)
        context.message = MSG(u'Version uploaded')



class FileExternalEdit(BaseView):

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
                    msg = MSG(u'This page is lock by another user')
                    return context.come_back(message=msg, goto='.')

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



class FileBacklinks(FolderBrowseContent):
    """Backlinks are the list of objects pointing to this object.  This view
    answers the question "where is this object used?" You'll see all WebPages
    and WikiPages (for example) referencing it.  If the list is empty, you can
    consider it is "orphan".
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Backlinks")
    icon = 'button_rename.png'

    search_template = None
    search_schema = {}

    # Skip AddResourceMenu
    context_menus = []

    def get_table_columns(self, resource, context):
        cols = FolderBrowseContent.get_table_columns(self, resource, context)
        return [ (name, title) for name, title in cols if name != 'checkbox' ]


    def get_items(self, resource, context):
        query = EqQuery('links', str(resource.get_abspath()))
        return context.root.search(query)


    def get_actions(self, resource, context, results):
        return []



class ImageThumbnail(BaseView):

    access = True

    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        width = context.get_form_value('width', type=Integer, default=48)
        height = context.get_form_value('height', type=Integer, default=48)

        data, format = resource.handler.get_thumbnail(width, height)
        if data is None:
            object = resource.get_resource('/ui/icons/48x48/image.png')
            data = object.to_str()
            format = 'png'

        response = context.response
        response.set_header('Content-Type', 'image/%s' % format)
        return data



class ImageView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Image_view.xml'

    def get_namespace(self, resource, context):
        path = context.site_root.get_pathto(resource)
        return {'src': '/%s/;download' % path}



# FIXME This is broken, check http://alistapart.com/articles/byebyeembed
class VideoView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Video_view.xml'


    def get_namespace(self, resource, context):
        return {'format': resource.handler.get_mimetype()}



class ArchiveView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/binary/Archive_view.xml'

    def get_namespace(self, resource, context):
        contents = resource.handler.get_contents()
        return {
            'contents': '\n'.join(contents)}

