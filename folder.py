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
from itools.xapian import PhraseQuery

# Import from ikaaro
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent, Folder_LastChanges
from folder_views import Folder_NewResource, Folder_Orphans, Folder_Thumbnail
from folder_views import Folder_PreviewContent, Folder_Rename, Folder_View
from registry import register_resource_class, get_resource_class
from resource_ import DBResource



class Folder(DBResource):

    class_id = 'folder'
    class_version = '20071215'
    class_title = MSG(u'Folder')
    class_description = MSG(u'Organize your files and documents with folders.')
    class_icon16 = 'icons/16x16/folder.png'
    class_icon48 = 'icons/48x48/folder.png'
    class_views = ['view', 'browse_content', 'preview_content', 'edit']
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

        cls = get_resource_class(format, is_file=is_file)
        return cls(metadata)


    def update_links(self, new_name, base_path):
        """The resource must update its links to itself and to its content
        """
        # Check referencial-integrity
        catalog = get_context().server.catalog
        # The catalog is not available when updating (icms-update.py)
        # FIXME We do not guarantee referencial-integrity when updating
        if catalog is None:
            return

        old_base_path = self.get_abspath()
        new_base_path = base_path.resolve2(new_name)
        for resource in self.traverse_resources():
            # Old and new paths
            old_path = resource.get_abspath()
            pathto = old_base_path.get_pathto(old_path)
            new_path = new_base_path.resolve2(pathto)

            # Get all the resources that have a link to this resource
            query = PhraseQuery('links', str(old_path))
            results = catalog.search(query).get_documents()
            for result in results:
                resource = self.get_resource(result.abspath)
                resource.change_link(old_path, new_path)


    def del_resource(self, name):
        context = get_context()
        resource = self.get_resource(name)

        # Check referencial-integrity
        catalog = context.server.catalog
        # The catalog is not available when updating (icms-update.py)
        # FIXME We do not guarantee referencial-integrity when updating
        if catalog is not None:
            # FIXME Check sub-resources too
            path = str(resource.get_abspath())
            results = catalog.search(links=path)
            if results.get_n_documents() > 0:
                message = 'cannot delete, resource "%s" is referenced' % path
                raise ConsistencyError, message

        # Events, remove
        context.server.remove_resource(resource)
        # Remove
        folder = self.handler
        folder.del_handler('%s.metadata' % name)
        for handler in resource.get_handlers():
            if folder.has_handler(handler.uri):
                folder.del_handler(handler.uri)


    def _resolve_source_target(self, source, target):
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

        # Load the handlers so they are of the right class, for resources
        # like that define explicitly the handler class.  This fixes for
        # instance copy&cut&paste of a tracker in a just started server.
        # TODO this is a work-around, there should be another way to define
        # explicitly the handler class.
        resource = self.get_resource(source)
        if isinstance(resource, Folder):
            for resource in resource.traverse_resources():
                resource.load_handlers()
        else:
            resource.load_handlers()

        return source_uri, target_uri


    def copy_resource(self, source, target):
        server = get_context().server

        # Find out the source and target absolute URIs
        source_uri, target_uri = self._resolve_source_target(source, target)
        new_name = target_uri.path[-1]

        # Get the source resource
        resource = self.get_resource(source)

        # Copy the metadata
        folder = self.handler
        folder.copy_handler('%s.metadata' % source_uri,
                            '%s.metadata' % target_uri)
        # Copy the content
        for old_name, new_name in resource.rename_handlers(new_name):
            if old_name is None:
                continue
            src_uri = source_uri.resolve(old_name)
            dst_uri = target_uri.resolve(new_name)
            if folder.has_handler(src_uri):
                folder.copy_handler(src_uri, dst_uri)

        # Events, add
        resource = self.get_resource(target)
        server.add_resource(resource)


    def move_resource(self, source, target):
        server = get_context().server

        # Find out the source and target absolute URIs
        source_uri, target_uri = self._resolve_source_target(source, target)
        new_name = target_uri.path[-1]

        # Get the source resource
        resource = self.get_resource(source)

        # Update the links to the resources that are to be moved
        resource.update_links(target, self.get_abspath())
        # Events, remove
        server.remove_resource(resource)

        # Move the metadata
        folder = self.handler
        folder.move_handler('%s.metadata' % source_uri,
                            '%s.metadata' % target_uri)
        # Move the content
        for old_name, new_name in resource.rename_handlers(new_name):
            if old_name is None:
                continue
            src_uri = source_uri.resolve(old_name)
            dst_uri = target_uri.resolve(new_name)
            if folder.has_handler(src_uri):
                folder.move_handler(src_uri, dst_uri)

        # Events, add
        resource = self.get_resource(target)
        server.add_resource(resource)


    def traverse_resources(self):
        yield self
        for name in self._get_names():
            resource = self.get_resource(name)
            if isinstance(resource, Folder):
                for x in resource.traverse_resources():
                    yield x
            else:
                yield resource


    def search_resources(self, cls=None, format=None, state=None):
        if cls is None:
            cls = DBResource

        for resource in self.get_resources():
            # Filter by base class
            if not isinstance(resource, cls):
                continue
            # Filter by class_id
            if format is not None and resource.metadata.format != format:
                continue
            # Filter by workflow state
            if state is not None and resource.get_workflow_state() != state:
                continue
            # All filters passed
            yield resource


    def get_human_size(self):
        names = self.get_names()
        size = len(names)

        return MSG(u'$n obs').gettext(n=size)


    #######################################################################
    # User interface
    #######################################################################
    def get_view(self, name, query=None):
        # Add resource form
        if name == 'new_resource':
            if query is not None and 'type' in query:
                view = get_resource_class(query['type']).new_instance
                if isinstance(view, BaseView):
                    return view

        # Default
        return DBResource.get_view(self, name, query)


    #######################################################################
    # Views
    view = Folder_View()
    new_resource = Folder_NewResource()
    browse_content = Folder_BrowseContent()
    rename = Folder_Rename()
    preview_content = Folder_PreviewContent()
    last_changes = Folder_LastChanges()
    orphans = Folder_Orphans()
    thumb = Folder_Thumbnail()



###########################################################################
# Register
###########################################################################
register_resource_class(Folder)
register_resource_class(Folder, format="application/x-not-regular-file")
