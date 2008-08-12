# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
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
from datetime import datetime, timedelta
from mimetypes import guess_all_extensions, guess_type

# Import from itools
from itools.datatypes import Boolean, FileName, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import File as FileHandler, guess_encoding, checkid
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.stl import stl
from itools.uri import get_reference
from itools.web import BaseView, STLView, STLForm
from itools.xapian import EqQuery

# Import from ikaaro
from datatypes import FileDataType
from messages import *
from multilingual import Multilingual
from registry import register_object_class, get_object_class
from versioning import VersioningAware
from views import NewInstanceForm, BrowseForm
from workflow import WorkflowAware


###########################################################################
# Views
###########################################################################
class NewFileForm(NewInstanceForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Upload File')
    template = '/ui/file/new_instance.xml'
    schema = {
        'title': Unicode,
        'file': FileDataType(mandatory=True),
    }


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



class Download(BaseView):

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



class DownloadView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Download')
    icon = 'view.png'
    template = '/ui/file/download_form.xml'


    def get_namespace(self, resource, context):
        return {
            'url': '../' + resource.name,
            'title_or_name': resource.get_title(),
        }



class UploadForm(STLForm):

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
            context.message = u'Unexpected file of mimetype %s' % mimetype
            return

        # Replace
        try:
            handler.load_state_from_string(body)
        except:
            handler.load_state()
            context.message = u'Failed to load the file, may contain errors.'
        else:
            context.server.change_object(resource)
            context.message = u'Version uploaded'



class ExternalEdit(BaseView):

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
                    msg = u'This page is lock by another user'
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



class BacklinksView(BrowseForm):

    access = 'is_allowed_to_view'
    title = MSG(u"Backlinks")
    icon = 'button_rename.png'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['title']),
        'batchstart': Integer(default=0),
    }


    def get_namespace(self, resource, context):
        """Backlinks are the list of objects pointing to this object.
        This view answers the question "where is this object used?"
        You'll see all WebPages and WikiPages (for example) referencing it.
        If the list is empty, you can consider it is "orphan".
        """
        from widgets import table

        # Get the form values
        query = context.query
        sortby = query['sortby']
        sortorder = query['sortorder']

        # Build the query
        search_query = EqQuery('links', str(resource.get_abspath()))

        # Build the namespace
        namespace = resource.browse_namespace(16, sortby, sortorder,
                                              batchsize=20, query=search_query)

        # The column headers
        columns = [
            ('name', MSG(u'Name')),
            ('title', MSG(u'Title')),
            ('format', MSG(u'Type')),
            ('mtime', MSG(u'Last Modified')),
            ('last_author', MSG(u'Last Author')),
            ('size', MSG(u'Size')),
            ('workflow_state', MSG(u'State'))
        ]

        # Remove the checkboxes
        objects = namespace['objects']
        for line in objects:
            line['checkbox'] = False

        # Go
        namespace['table'] = table(columns, objects, sortby, sortorder)
        return namespace



###########################################################################
# Model
###########################################################################
file_description = u'Upload office documents, images, media files, etc.'

class File(WorkflowAware, VersioningAware):

    class_id = 'file'
    class_version = '20071216'
    class_title = MSG(u'File')
    class_description = MSG(file_description)
    class_icon16 = 'icons/16x16/file.png'
    class_icon48 = 'icons/48x48/file.png'
    class_views = ['view', 'externaledit', 'upload', 'backlinks',
                   'edit_metadata', 'edit_state', 'history']
    class_handler = FileHandler


    @staticmethod
    def _make_object(cls, folder, name, body=None, filename=None,
                     extension=None, **kw):
        VersioningAware._make_object(cls, folder, name, filename=filename,
                                     **kw)
        # Add the body
        if body is not None:
            handler = cls.class_handler(string=body)
            extension = extension or handler.class_extension
            name = FileName.encode((name, extension, None))
            folder.set_handler(name, handler)


    def get_all_extensions(self):
        format = self.metadata.format
        # FIXME This is a hack, compression encodings are not yet properly
        # supported (to do for the next major version).
        if format == 'application/x-gzip':
            extensions = ['gz', 'tgz']
        elif format == 'application/x-bzip2':
            extensions = ['bz2', 'tbz2']
        else:
            cls = self.class_handler
            extensions = [ x[1:] for x in guess_all_extensions(format) ]
            if cls.class_extension in extensions:
                extensions.remove(cls.class_extension)
            extensions.insert(0, cls.class_extension)
        return extensions


    def get_handler(self):
        # Already loaded
        if self._handler is not None:
            return self._handler

        # Not yet loaded
        database = self.metadata.database
        base = self.metadata.uri
        cls = self.class_handler

        # Check the handler exists
        extensions = self.get_all_extensions()
        for extension in extensions:
            name = FileName.encode((self.name, extension, None))
            uri = base.resolve(name)
            # Found
            if database.has_handler(uri):
                self._handler = database.get_handler(uri, cls=cls)
                return self._handler

        # Not found, build a dummy one
        name = FileName.encode((self.name, cls.class_extension, None))
        uri = base.resolve(name)
        handler = cls()
        handler.database = database
        handler.uri = uri
        handler.timestamp = None
        handler.dirty = datetime.now()
        database.cache[uri] = handler
        self._handler = handler
        return self._handler

    handler = property(get_handler, None, None, '')


    def rename_handlers(self, new_name):
        folder = self.parent.handler
        old_name = self.name
        for extension in self.get_all_extensions():
            old = FileName.encode((old_name, extension, None))
            if folder.has_handler(old):
                return [(old, FileName.encode((new_name, extension, None)))]
        return None, None


    #######################################################################
    # Metadata
    #######################################################################
    @classmethod
    def get_metadata_schema(cls):
        schema = VersioningAware.get_metadata_schema()
        schema.update(WorkflowAware.get_metadata_schema())
        schema['filename'] = String
        return schema


    #######################################################################
    # Versioning & Indexing
    #######################################################################
    def to_text(self):
        return self.handler.to_text()


    def get_size(self):
        sizes = [ len(x.to_str()) for x in self.get_handlers() ]
        # XXX Maybe not the good algo
        return max(sizes)


    #######################################################################
    # UI
    #######################################################################
    def get_human_size(self):
        file = self.handler
        bytes = len(file.to_str())
        size = bytes / 1024.0
        if size >= 1024:
            size = size / 1024.0
            str = MSG(u'%.01f MB')
        else:
            str = MSG(u'%.01f KB')

        return str.gettext() % size


    def get_content_type(self):
        return self.handler.get_mimetype()


    #######################################################################
    # Views
    #######################################################################
    new_instance = NewFileForm()
    download = Download()
    view = DownloadView()

    externaledit = STLView(
        access='is_allowed_to_edit',
        title=MSG(u'External Editor'),
        icon='button_external.png',
        template='/ui/file/externaledit.xml',
    )

    external_edit = ExternalEdit()
    upload = UploadForm()
    backlinks = BacklinksView()



###########################################################################
# Register
###########################################################################
register_object_class(File)
register_object_class(File, format="application/octet-stream")
