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
from itools.database import AndQuery, NotQuery, PhraseQuery
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import Folder as FolderHandler
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.i18n import guess_language
from itools.uri import Path
from itools.web import get_context, BaseView

# Import from ikaaro
from datatypes import guess_mimetype
from exceptions import ConsistencyError
from folder_views import Folder_BrowseContent
from folder_views import Folder_NewResource, Folder_Orphans, Folder_Thumbnail
from folder_views import Folder_PreviewContent, Folder_Rename, Folder_View
from metadata import Metadata
from multilingual import Multilingual
from registry import register_resource_class, get_resource_class
from registry import _lookup_class_id, resources_registry
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
                   'links', 'backlinks', 'commit_log']
    class_handler = FolderHandler


    # Aggregation relationship (what a generic folder can contain)
    __fixed_handlers__ = []


    #########################################################################
    # Gallery properties
    SIZE_STEPS = (32, 48, 64, 128, 256, 512)


    def get_document_types(self):
        document_types = []
        for ancestor_class in reversed(self.__class__.__mro__):
            items = ancestor_class.__dict__.get('_register_document_types')
            if items:
                document_types.extend(items)

        # class_id to class
        return [ get_resource_class(class_id) for class_id in document_types ]


    def get_files_to_archive(self, content=False):
        metadata = self.metadata.key
        if content is True:
            folder = self.handler.key
            return [metadata, folder]
        return [metadata]


    #######################################################################
    # API
    #######################################################################
    def make_resource(self, name, cls, **kw):
        context = get_context()
        # Make the metadata
        format = kw.pop('format', None)
        metadata = Metadata(cls=cls, format=format)
        metadata.set_property('mtime', context.timestamp)
        self.handler.set_handler('%s.metadata' % name, metadata)
        # Initialize
        resource = self.get_resource(name)
        resource.init_resource(**kw)
        # Ok
        context.database.add_resource(resource)
        return resource


    def _make_file(self, name, filename, mimetype, body, default_language):
        kk, extension, language = FileName.decode(filename)
        name = name or kk
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
        kw = {'format': class_id, 'filename': filename}
        if issubclass(cls, Multilingual):
            if language is None:
                text = cls.class_handler(string=body).to_text()
                language = guess_language(text) or default_language
            kw['language'] = language
        else:
            kw['extension'] = extension

        return self.make_resource(name, cls, body=body, **kw)


    def extract_archive(self, handler, language, filter=None, postproc=None,
                        update=False):
        change_resource = get_context().database.change_resource
        for path_str in handler.get_contents():
            # 1. Skip folders
            path = Path(path_str)
            if path.endswith_slash:
                continue

            # 2. Create parent folders if needed
            folder = self
            for name in path[:-1]:
                subfolder = folder.get_resource(name, soft=True)
                if subfolder is None:
                    folder = folder.make_resource(name, Folder)
                else:
                    folder = subfolder

            # 3. Get the new body
            name = path[-1]
            body = handler.get_file(path_str)
            mimetype = guess_mimetype(name, 'application/octet-stream')
            if filter:
                body = filter(path_str, mimetype, body)
                if body is None:
                    continue

            # 4. Update or make file
            filename, extension, language = FileName.decode(name)
            file = folder.get_resource(filename, soft=True)
            if file:
                if update is False:
                    msg = 'unexpected resource at {path}'
                    raise RuntimeError, msg.format(path=path_str)
                if mimetype == 'text/html':
                    body = stream_to_str_as_xhtml(HTMLParser(body))
                old_body = file.handler.to_str()
                file.handler.load_state_from_string(body)
                if postproc:
                    postproc(file)
                # FIXME Comparing the bytes does not work for XML, so we use
                # this weak heuristic
                if len(old_body) != len(file.handler.to_str()):
                    change_resource(file)
            else:
                # Case 1: the resource does not exist
                file = folder._make_file(None, name, mimetype, body, language)
                if postproc:
                    postproc(file)


    def can_paste(self, source):
        """Is the source resource can be pasted into myself.
        """
        allowed_types = tuple(self.get_document_types())
        return isinstance(source, allowed_types)


    def _get_names(self):
        folder = self.handler
        return [ x[:-9] for x in folder.get_handler_names()
                 if x[-9:] == '.metadata' ]


    def _get_resource(self, name):
        # (1) Metadata
        folder = self.handler
        try:
            metadata = folder.get_handler('%s.metadata' % name)
        except LookupError:
            return None

        # (2) Class id
        format = metadata.format
        class_id = _lookup_class_id(format)
        if class_id is None:
            fs = metadata.database.fs
            key = fs.resolve2(folder.key, name)
            if fs.exists(key):
                is_file = fs.is_file(key)
            else:
                # FIXME This is just a guess, it may fail.
                is_file = '/' in format

            if is_file:
                class_id = 'application/octet-stream'
            else:
                class_id = 'application/x-not-regular-file'

        # Ok
        cls = resources_registry[class_id]
        return cls(metadata)


    def del_resource(self, name, soft=False, ref_action='restrict'):
        """ref_action allows to specify which action is done before deleting
        the resource.
        ref_action can take 2 values:
        - 'restrict' (default value): do an integrity check
        - 'force': do nothing
        """

        database = get_context().database
        resource = self.get_resource(name, soft=soft)
        if soft and resource is None:
            return

        # Referential action
        if ref_action == 'restrict':
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
        elif ref_action == 'force':
            # Do not check referencial-integrity
            pass
        else:
            raise ValueError, 'Incorrect ref_action "%s"' % ref_action

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
        for resource in source.traverse_resources():
            resource.load_handlers()

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

        # Get the source and target resources
        source = self.get_resource(source_path)
        parent_path = target_path.resolve2('..')
        target_parent = self.get_resource(parent_path)

        # Cannot move a resource to a subdirectory of itself
        abspath = self.get_canonical_path()
        aux = source.get_canonical_path()
        if aux.get_prefix(abspath) == aux:
            message = 'cannot move a resource to a subdirectory of itself'
            raise ConsistencyError, message

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
            for x in resource.traverse_resources():
                yield x


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


    #######################################################################
    # User interface
    #######################################################################
    def get_view(self, name, query=None):
        # Add resource form
        if name == 'new_resource':
            if query:
                class_id = query.get('type')
                if class_id:
                    view = get_resource_class(class_id).new_instance
                    if isinstance(view, BaseView):
                        return view

        # Default
        return DBResource.get_view(self, name, query)


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
