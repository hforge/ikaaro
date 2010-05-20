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
from itools.uri import Path
from itools.web import get_context, BaseView
from itools.xapian import AndQuery, NotQuery, PhraseQuery

# Import from ikaaro
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent
from folder_views import Folder_NewResource, Folder_Orphans, Folder_Thumbnail
from folder_views import Folder_PreviewContent, Folder_Rename, Folder_View
from registry import register_resource_class, get_resource_class
from registry import get_document_types
from resource_ import DBResource
from utils import get_base_path_query



class Folder(DBResource):

    class_id = 'folder'
    class_version = '20071215'
    class_title = MSG(u'Folder')
    class_description = MSG(u'Organize your files and documents with folders.')
    class_icon16 = 'icons/16x16/folder.png'
    class_icon48 = 'icons/48x48/folder.png'
    class_views = ['view', 'browse_content', 'preview_content', 'edit',
                   'backlinks', 'commit_log']
    class_handler = FolderHandler


    # Aggregation relationship (what a generic folder can contain)
    __fixed_handlers__ = []


    #########################################################################
    # Gallery properties
    DEFAULT_SIZE = 128
    MIN_SIZE = 32
    MAX_SIZE = 512
    SIZE_STEPS = (32, 48, 64, 128, 256, 512)


    def get_document_types(self):
        return get_document_types()


    def get_files_to_archive(self, content=False):
        metadata = self.metadata.key
        if content is True:
            folder = self.handler.key
            return [metadata, folder]
        return [metadata]


    ########################################################################
    # Cut & Paste Resources
    ########################################################################
    def can_paste(self, source):
        """Is the source resource can be pasted into myself.
        """
        allowed_types = tuple(self.get_document_types())
        return isinstance(source, allowed_types)


    #######################################################################
    # API
    #######################################################################
    def _get_names(self):
        folder = self.handler
        return [ x[:-9] for x in folder.get_handler_names()
                 if x[-9:] == '.metadata' ]


    def _get_resource(self, name):
        # Look for the resource
        folder = self.handler
        try:
            metadata = folder.get_handler('%s.metadata' % name)
        except LookupError:
            return None

        # Format (class id)
        format = metadata.format

        # File or folder
        fs = metadata.database.fs
        key = fs.resolve2(folder.key, name)
        if fs.exists(key):
            is_file = fs.is_file(key)
        else:
            # FIXME This is just a guess, it may fail.
            is_file = '/' in format

        # Ok
        cls = get_resource_class(format, is_file=is_file)
        return cls(metadata)


    def del_resource(self, name, soft=False):
        database = get_context().database
        resource = self.get_resource(name, soft=soft)
        if soft and resource is None:
            return

        # Check referencial-integrity
        catalog = database.catalog
        # FIXME Check sub-resources too
        path = str(resource.get_canonical_path())
        query_base_path = get_base_path_query(path)
        query = AndQuery(PhraseQuery('links', path),
                         NotQuery(query_base_path))
        results = catalog.search(query)
        if len(results):
            message = 'cannot delete, resource "%s" is referenced' % path
            raise ConsistencyError, message

        # Events, remove
        database.remove_resource(resource)
        # Remove
        fs = database.fs
        for handler in resource.get_handlers():
            # Skip empty folders and phantoms
            if fs.exists(handler.key):
                database.del_handler(handler.key)
        self.handler.del_handler('%s.metadata' % name)


    def _resolve_source_target(self, source_path, target_path):
        if type(source_path) is not Path:
            source_path = Path(source_path)
        if type(target_path) is not Path:
            target_path = Path(target_path)

        # Load the handlers so they are of the right class, for resources
        # like that define explicitly the handler class.  This fixes for
        # instance copy&cut&paste of a tracker in a just started server.
        # TODO this is a work-around, there should be another way to define
        # explicitly the handler class.
        source = self.get_resource(source_path)
        if isinstance(source, Folder):
            for resource in source.traverse_resources():
                resource.load_handlers()
        else:
            source.load_handlers()

        return source_path, target_path


    def copy_resource(self, source_path, target_path):
        # Find out the source and target absolute URIs
        source_path, target_path = self._resolve_source_target(source_path,
                                                               target_path)

        # Get the source and target resources
        source = self.get_resource(source_path)
        parent_path = target_path.resolve2('..')
        target_parent = self.get_resource(parent_path)

        # Check compatibility
        if (not target_parent.can_paste(source)
                or not source.can_paste_into(target_parent)):
            message = 'resource type "%r" cannot be copied into type "%r"'
            raise ConsistencyError, message % (source, target_parent)

        # Copy the metadata
        folder = self.handler
        folder.copy_handler('%s.metadata' % source_path,
                            '%s.metadata' % target_path)

        # Copy the content
        database = self.metadata.database
        fs =  database.fs
        new_name = target_path.get_name()
        for old_name, new_name in source.rename_handlers(new_name):
            if old_name is None:
                continue
            src_key = fs.resolve(source_path, old_name)
            dst_key = fs.resolve(target_path, new_name)
            if folder.has_handler(src_key):
                folder.copy_handler(src_key, dst_key)

        # Events, add
        resource = self.get_resource(target_path)
        database.add_resource(resource)


    def move_resource(self, source_path, target_path):
        # Find out the source and target absolute URIs
        source_path, target_path = self._resolve_source_target(source_path,
                                                               target_path)

        # Cannot move a resource to a subdirectory of itself
        abspath = self.get_canonical_path()
        if source_path.get_prefix(abspath) == source_path:
            message = 'cannot move a resource to a subdirectory of itself'
            raise ConsistencyError, message

        # Get the source and target resources
        source = self.get_resource(source_path)
        parent_path = target_path.resolve2('..')
        target_parent = self.get_resource(parent_path)

        # Check compatibility
        if (not target_parent.can_paste(source)
                or not source.can_paste_into(target_parent)):
            message = 'resource type "%r" cannot be moved into type "%r"'
            raise ConsistencyError, message % (source, target_parent)

        # Events, remove
        database = self.metadata.database
        new_path = self.get_canonical_path().resolve2(target_path)
        database.move_resource(source, new_path)

        # Move the metadata
        folder = self.handler
        folder.move_handler('%s.metadata' % source_path,
                            '%s.metadata' % target_path)
        # Move the content
        fs = database.fs
        new_name = target_path.get_name()
        for old_name, new_name in source.rename_handlers(new_name):
            if old_name is None:
                continue
            src_key = fs.resolve(source_path, old_name)
            dst_key = fs.resolve(target_path, new_name)
            if folder.has_handler(src_key):
                folder.move_handler(src_key, dst_key)


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

        return MSG(u'{n} obs').gettext(n=size)


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
    orphans = Folder_Orphans()
    thumb = Folder_Thumbnail()



###########################################################################
# Register
###########################################################################
register_resource_class(Folder, format="application/x-not-regular-file")
