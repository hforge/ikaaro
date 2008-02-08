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
from itools.datatypes import FileName, String, Unicode
from itools.handlers import File as FileHandler, guess_encoding, checkid
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.stl import stl
from itools.uri import get_reference
from itools.catalog import EqQuery

# Import from ikaaro
from messages import *
from multilingual import Multilingual
from registry import register_object_class, get_object_class
from versioning import VersioningAware
from utils import get_file_parts
from workflow import WorkflowAware



class File(WorkflowAware, VersioningAware):

    class_id = 'file'
    class_version = '20071216'
    class_title = u'File'
    class_description = u'Upload office documents, images, media files, etc.'
    class_icon16 = 'icons/16x16/file.png'
    class_icon48 = 'icons/48x48/file.png'
    class_views = [['download_form'],
                   ['externaledit', 'upload_form'],
                   ['backlinks'],
                   ['edit_metadata_form'],
                   ['state_form'],
                   ['history_form']]
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
        handler.dirty = True
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


    @staticmethod
    def new_instance_form(cls, context):
        namespace = {}
        namespace['class_id'] = cls.class_id
        namespace['title'] = context.get_form_value('title', type=Unicode)

        handler = context.root.get_object('ui/file/new_instance.xml')
        return stl(handler, namespace)


    @staticmethod
    def new_instance(cls, container, context):
        file = context.get_form_value('file')
        title = context.get_form_value('title', type=Unicode)
        # The upload file is mandatory
        if file is None:
            return context.come_back(MSG_EMPTY_FILENAME)

        filename, mimetype, body = get_file_parts(file)

        # Check the filename is good
        name = title.strip() or filename
        name = checkid(name)
        if name is None:
            return context.come_back(MSG_BAD_NAME)

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
                    language = container.get_content_language(context)

        # Check the name is free
        if container.has_object(name):
            message = (u'There is already another object with this name. '
                       u'Please type a title to choose a different name.')
            return context.come_back(message)

        # Build the object
        kw = {'format': class_id, 'filename': filename}
        if issubclass(cls, Multilingual):
            kw['language'] = language
        else:
            kw['extension'] = type
        object = cls.make_object(cls, container, name, body, **kw)
        # The title
        language = container.get_content_language(context)
        object.metadata.set_property('title', title, language=language)

        goto = './%s/;%s' % (name, object.get_firstview())
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)


    GET__mtime__ = VersioningAware.get_mtime
    def GET(self, context):
        return self.download(context)


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
    # User Interface
    #######################################################################
    def get_human_size(self):
        file = self.handler
        bytes = len(file.to_str())
        size = bytes / 1024.0
        if size >= 1024:
            size = size / 1024.0
            str = u'%.01f MB'
        else:
            str = u'%.01f KB'

        return self.gettext(str) % size


    def get_context_menu_base(self):
        return self.parent


    #######################################################################
    # Download
    download_form__access__ = 'is_allowed_to_view'
    download_form__label__ = u'View'
    download_form__sublabel__ = u'Download'
    download_form__icon__ = 'view.png'
    def download_form(self, context):
        namespace = {}
        namespace['url'] = '../' + self.name
        namespace['title_or_name'] = self.get_title()
        handler = self.get_object('/ui/file/download_form.xml')
        return stl(handler, namespace)


    def get_content_type(self):
        return self.handler.get_mimetype()


    download__access__ = 'is_allowed_to_view'
    download__mtime__ = VersioningAware.get_mtime
    def download(self, context):
        response = context.response
        # Filename
        filename = self.get_property('filename')
        if filename is not None:
            response.set_header('Content-Disposition',
                                'inline; filename="%s"' % filename)
        # Content-Type
        response.set_header('Content-Type', self.get_content_type())
        return self.handler.to_str()


    #######################################################################
    # Edit / External
    externaledit__access__ = 'is_allowed_to_edit'
    externaledit__label__ = u'Edit'
    externaledit__sublabel__ = u'External'
    externaledit__icon__ = 'button_external.png'
    def externaledit(self, context):
        handler = self.get_object('/ui/file/externaledit.xml')
        return stl(handler)


    external_edit__access__ = 'is_allowed_to_edit'
    def external_edit(self, context):
        # TODO check if zopeedit really needs the meta_type.
        encoding = context.get_form_value('encoding')

        # Get the context, request and response
        request, response = context.request, context.response

        uri = context.uri
        uri_string = '%s://%s/%s' % (uri.scheme, uri.authority, uri.path[:-1])
        uri = get_reference(uri_string)
        r = ['url:%s' % str(uri),
             'meta_type:toto', # XXX Maybe something more meaningful than toto?
             'content_type:%s' % self.handler.get_mimetype(),
             'cookie:%s' % request.get_cookies_as_str()]

        title = self.get_property('title')
        if title:
            title = title.encode(encoding or 'UTF-8')
        else:
            title = self.name
        r.append('title:%s' % title)

        if self.is_locked():
            lock = self.get_lock()
            # locks expire after 1 hour
            if lock.lock_timestamp + timedelta(hours=1) < datetime.now():
                self.unlock()
                context.commit = True
            else:
                # always borrow lock from same user
                if lock.username == context.user.name:
                    r.append('lock-token:%s' % lock.key)
                    r.append('borrow_lock:1')
                else:
                    goto = ';%s' % self.get_firstview()
                    msg = u'This page is lock by another user'
                    return context.come_back(message=msg, goto=goto)

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
            r.append(self.handler.to_str())
        else:
            r.append(self.handler.to_str(encoding))

        data = '\n'.join(r)

        response.set_header('Content-Type', 'application/x-zope-edit')
        return data


    #######################################################################
    # Edit / Upload
    upload_form__access__ = 'is_allowed_to_edit'
    upload_form__label__ = u'Edit'
    upload_form__sublabel__ = u'Replace'
    upload_form__icon__ = 'button_upload.png'
    def upload_form(self, context):
        handler = self.get_object('/ui/file/upload.xml')
        return stl(handler)


    upload__access__ = 'is_allowed_to_edit'
    def upload(self, context):
        file = context.get_form_value('file')
        if file is None:
            return context.come_back(u'No file has been entered.')

        # Check wether the handler is able to deal with the uploaded file
        filename, mimetype, body = get_file_parts(file)
        if mimetype != self.handler.get_mimetype():
            message = u'Unexpected file of mimetype ${mimetype}.'
            return context.come_back(message, mimetype=mimetype)

        # Replace
        try:
            self.handler.load_state_from_string(body)
        except:
            self.handler.load_state()
            message = u'Failed to load the file, may contain errors.'
            return context.come_back(message)

        context.server.change_object(self)
        return context.come_back(u'Version uploaded.')


    #######################################################################
    # UI / Backlinks
    #######################################################################
    backlinks__access__ = 'is_allowed_to_view'
    backlinks__label__ = u"Backlinks"
    backlinks__title__ = u"Backlinks"
    backlinks__icon__ = 'button_rename.png'
    def backlinks(self, context, sortby=['title'], sortorder='up',
                  batchsize=20):
        """Backlinks are the list of objects pointing to this object.
        This view answers the question "where is this object used?"
        You'll see all WebPages and WikiPages (for example) referencing it.
        If the list is empty, you can consider it is "orphan".
        """
        from widgets import table

        root = context.root

        # Get the form values
        sortby = context.get_form_values('sortby', default=sortby)
        sortorder = context.get_form_value('sortorder', default=sortorder)

        # Build the query
        query = EqQuery('links', str(self.get_abspath()))

        # Build the namespace
        namespace = self.browse_namespace(16, sortby, sortorder, batchsize,
                                          query=query)
        namespace['search_fields'] = None

        # The column headers
        columns = [
            ('name', u'Name'), ('title', u'Title'), ('format', u'Type'),
            ('mtime', u'Last Modified'), ('last_author', u'Last Author'),
            ('size', u'Size'), ('workflow_state', u'State')]

        # Remove the checkboxes
        objects = namespace['objects']
        for line in objects:
            line['checkbox'] = False

        # Go
        namespace['table'] = table(columns, objects, sortby, sortorder,
                                   gettext=self.gettext)

        template = self.get_object('/ui/folder/browse_list.xml')
        return stl(template, namespace)


    #######################################################################
    # Update
    #######################################################################
    def update_20071216(self):
        folder = self.parent.handler
        # Add the "filename" field
        metadata = self.metadata
        filename = self.name
        metadata.set_property('filename', filename)
        # Normalize the filename
        name, extension, language = FileName.decode(filename)
        name = checkid(name)
        # Fix the mimetype
        if extension is not None:
            extension = extension.lower()
            if '/' not in metadata.format:
                mimetype, encoding = guess_type('.%s' % extension)
                if mimetype is not None:
                    if metadata.format != mimetype:
                        metadata.format = mimetype
        # Rename metadata
        folder.move_handler('%s.metadata' % self.name, '%s.metadata' % name)
        # Rename handler
        if extension is None:
            extension = self.class_handler.class_extension
        name = FileName.encode((name, extension, None))
        if name != self.name:
            folder.move_handler(self.name, name)



###########################################################################
# Register
###########################################################################
register_object_class(File)
register_object_class(File, format="application/octet-stream")
