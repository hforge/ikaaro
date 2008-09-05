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
from datetime import datetime
from mimetypes import guess_all_extensions

# Import from itools
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers import File as FileHandler
from itools.vfs import FileName
from itools.web import STLView

# Import from ikaaro
from folder_views import FolderBrowseContent
from registry import register_object_class
from versioning import VersioningAware
from workflow import WorkflowAware
from file_views import FileNewInstance, FileDownload, FileView
from file_views import FileExternalEdit, FileUpload, FileBacklinks



class File(WorkflowAware, VersioningAware):

    class_id = 'file'
    class_version = '20071216'
    class_title = MSG(u'File')
    class_description = MSG(
        u'Upload office documents, images, media files, etc.')
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
    # User Interface
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

    # Views
    new_instance = FileNewInstance()
    download = FileDownload()
    view = FileView()
    externaledit = STLView(
        access='is_allowed_to_edit',
        title=MSG(u'External Editor'),
        icon='button_external.png',
        template='/ui/file/externaledit.xml')
    external_edit = FileExternalEdit()
    upload = FileUpload()
    backlinks = FileBacklinks()



###########################################################################
# Register
###########################################################################
register_object_class(File)
register_object_class(File, format="application/octet-stream")
