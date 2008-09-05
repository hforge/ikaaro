# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
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

# Import from itools
from itools.gettext import MSG
from itools.handlers import Folder as FolderHandler
from itools import vfs
from itools.web import get_context, BaseView

# Import from ikaaro
from exceptions import ConsistencyError
from folder_views import FolderBrowseContent, FolderLastChanges
from folder_views import FolderNewResource, FolderOrphans
from folder_views import FolderPreviewContent, FolderRename, FolderView
from registry import register_object_class, get_object_class
from resources import DBResource



class Folder(DBResource):

    class_id = 'folder'
    class_version = '20071215'
    class_title = MSG(u'Folder')
    class_description = MSG(u'Organize your files and documents with folders.')
    class_icon16 = 'icons/16x16/folder.png'
    class_icon48 = 'icons/48x48/folder.png'
    class_views = ['browse_content', 'preview_content', 'new_resource',
                   'edit_metadata']
    class_handler = FolderHandler


    #########################################################################
    # Aggregation relationship (what a generic folder can contain)
    class_document_types = []

    __fixed_handlers__ = []


    #########################################################################
    # Gallery properties
    DEFAULT_SIZE = 128
    MIN_SIZE = 32
    MAX_SIZE = 512
    SIZE_STEPS = (32, 48, 64, 128, 256, 512)


    @classmethod
    def register_document_type(cls, handler_class):
        cls.class_document_types.append(handler_class)


    def get_document_types(self):
        return self.class_document_types


    #######################################################################
    # API
    #######################################################################
    def _has_resource(self, name):
        folder = self.handler
        return folder.has_handler('%s.metadata' % name)


    def _get_names(self):
        folder = self.handler
        return [ x[:-9] for x in folder.get_handler_names()
                 if x[-9:] == '.metadata' ]


    def _get_resource(self, name):
        folder = self.handler
        metadata = folder.get_handler('%s.metadata' % name)
        format = metadata.format

        uri = folder.uri.resolve2(name)
        if vfs.exists(uri):
            is_file = vfs.is_file(uri)
        else:
            # FIXME This is just a guess, it may fail.
            is_file = '/' in format

        cls = get_object_class(format, is_file=is_file)
        return cls(metadata)


    def del_resource(self, name):
        object = self.get_resource(name)

        # Check referencial-integrity
        # FIXME Check sub-objects too
        path = str(object.abspath)
        root = self.get_root()
        results = root.search(links=path)
        n = results.get_n_documents()
        if n:
            message = 'cannot delete, object "%s" is referenced' % path
            raise ConsistencyError, message

        # Events, remove
        get_context().server.remove_object(object)
        # Remove
        folder = self.handler
        folder.del_handler('%s.metadata' % name)
        for handler in object.get_handlers():
            if folder.has_handler(handler.uri):
                folder.del_handler(handler.uri)


    def copy_resource(self, source, target):
        context = get_context()

        # Find out the source and target absolute URIs
        folder = self.handler
        if source[0] == '/':
            source_uri = self.get_root().handler.uri.resolve2(source[1:])
        else:
            source_uri = folder.uri.resolve2(source)
        if target[0] == '/':
            target_uri = self.get_root().handler.uri.resolve2(target[1:])
        else:
            target_uri = folder.uri.resolve2(target)
        old_name = source_uri.path[-1]
        new_name = target_uri.path[-1]

        # Copy the metadata
        folder.copy_handler('%s.metadata' % source_uri,
                            '%s.metadata' % target_uri)
        # Copy the content
        object = self.get_resource(source)
        for old_name, new_name in object.rename_handlers(new_name):
            if old_name is None:
                continue
            src_uri = source_uri.resolve(old_name)
            dst_uri = target_uri.resolve(new_name)
            if folder.has_handler(src_uri):
                folder.copy_handler(src_uri, dst_uri)

        # Events, add
        object = self.get_resource(target)
        context.server.add_object(object)


    def move_resource(self, source, target):
        context = get_context()
        # Events, remove
        object = self.get_resource(source)
        context.server.remove_object(object)

        # Find out the source and target absolute URIs
        folder = self.handler
        if source[0] == '/':
            source_uri = self.get_root().handler.uri.resolve2(source[1:])
        else:
            source_uri = folder.uri.resolve2(source)
        if target[0] == '/':
            target_uri = self.get_root().handler.uri.resolve2(target[1:])
        else:
            target_uri = folder.uri.resolve2(target)
        old_name = source_uri.path[-1]
        new_name = target_uri.path[-1]

        # Move the metadata
        folder.move_handler('%s.metadata' % source_uri,
                            '%s.metadata' % target_uri)
        # Move the content
        for old_name, new_name in object.rename_handlers(new_name):
            if old_name is None:
                continue
            src_uri = source_uri.resolve(old_name)
            dst_uri = target_uri.resolve(new_name)
            if folder.has_handler(src_uri):
                folder.move_handler(src_uri, dst_uri)

        # Events, add
        object = self.get_resource(target)
        context.server.add_object(object)


    def traverse_resources(self):
        yield self
        for name in self._get_names():
            object = self.get_resource(name)
            if isinstance(object, Folder):
                for x in object.traverse_resources():
                    yield x
            else:
                yield object


    def search_objects(self, path='.', format=None, state=None,
                       object_class=None):
        for object in self.get_resources(path):
            if not isinstance(object, DBResource):
                continue
            # Filter by base class
            cls = object_class
            if cls is not None and not isinstance(object, cls):
                continue
            # Filter by class_id
            if format is not None and object.metadata.format != format:
                continue
            # Filter by workflow state
            if state is not None and object.get_workflow_state() != state:
                continue
            # All filters passed
            yield object


    def get_human_size(self):
        names = self.get_names()
        size = len(names)

        return MSG(u'$n obs').gettext(n=size)


    #######################################################################
    # User interface
    #######################################################################
    def get_default_view_name(self):
        # Index page
        if self.has_resource('index'):
            return 'view'

        return DBResource.get_default_view_name(self)


    def get_view(self, name, query=None):
        # Add resource form
        if name == 'new_resource':
            if query is not None and 'type' in query:
                view = get_object_class(query['type']).new_instance
                if isinstance(view, BaseView):
                    return view

        # Default
        return DBResource.get_view(self, name, query)


    #######################################################################
    # Views
    view = FolderView()
    new_resource = FolderNewResource()
    browse_content = FolderBrowseContent()
    rename = FolderRename()
    preview_content = FolderPreviewContent()
    last_changes = FolderLastChanges()
    orphans = FolderOrphans()



###########################################################################
# Register
###########################################################################
register_object_class(Folder)
register_object_class(Folder, format="application/x-not-regular-file")
