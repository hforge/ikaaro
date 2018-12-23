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


# Import from the Standard Library
import fnmatch
from cStringIO import StringIO
from os.path import basename, dirname
from zipfile import ZipFile

# Import from itools
from itools.core import is_prototype
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import checkid
from itools.database import Metadata
from itools.database import AndQuery, PhraseQuery, NotQuery
from itools.html import XHTMLFile
from itools.i18n import guess_language
from itools.uri import Path
from itools.web import BaseView, get_context

# Import from ikaaro
from views.folder_views import Folder_BrowseContent, Folder_PreviewContent
from views.folder_views import Folder_Rename, Folder_NewResource, Folder_Thumbnail

# Import from ikaaro
from autoedit import AutoEdit
from database import Database
from datatypes import guess_mimetype
from exceptions import ConsistencyError
from messages import MSG_NAME_CLASH
from resource_ import DBResource
from utils import process_name, tidy_html, get_base_path_query



class Folder(DBResource):

    class_id = 'folder'
    class_version = '20071215'
    class_title = MSG(u'Folder')
    class_description = MSG(u'Organize your files and documents with folders.')
    class_icon16 = '/ui/ikaaro/icons/16x16/folder.png'
    class_icon48 = '/ui/ikaaro/icons/48x48/folder.png'
    class_views = ['view', 'browse_content', 'preview_content', 'edit',
                   'links', 'backlinks']


    #########################################################################
    # Gallery properties
    #########################################################################
    SIZE_STEPS = (32, 48, 64, 128, 256, 512)


    #########################################################################
    # Folder specific API
    #########################################################################

    def get_document_types(self):
        document_types = []
        for ancestor_class in reversed(self.__class__.__mro__):
            items = ancestor_class.__dict__.get('_register_document_types')
            if items:
                document_types.extend(items)

        # class_id to class
        database = self.database
        return [ database.get_resource_class(class_id)
                 for class_id in document_types ]


    def traverse_resources(self):
        yield self
        for name in self._get_names():
            resource = self.get_resource(name)
            for x in resource.traverse_resources():
                yield x


    def make_resource_name(self):
        max_id = -1
        for name in self.get_names():
            # Mixing explicit and automatically generated names is allowed
            try:
                id = int(name)
            except ValueError:
                continue
            if id > max_id:
                max_id = id

        return str(max_id + 1)


    def make_resource(self, name, cls, soft=False, **kw):
        # Automatic name
        if name is None:
            name = self.make_resource_name()

        # Make a resource somewhere else
        if '/' in name:
            path = dirname(name)
            name = basename(name)
            resource = self.get_resource(path)
            resource.make_resource(name, cls, soft=soft, **kw)
            return

        # Soft
        if soft is True:
            resource = self.get_resource(name, soft=True)
            if resource:
                return resource

        # Make the metadata
        metadata = Metadata(cls=cls)
        self.handler.set_handler('%s.metadata' % name, metadata)
        metadata.set_property('mtime', get_context().timestamp)
        # Initialize
        resource = self.get_resource(name)
        self.database.add_resource(resource)
        resource.init_resource(**kw)
        # Ok
        return resource


    def del_resource(self, name, soft=False, ref_action='restrict'):
        """ref_action allows to specify which action is done before deleting
        the resource.
        ref_action can take 2 values:
        - 'restrict' (default value): do an integrity check
        - 'force': do nothing
        """
        database = self.database
        resource = self.get_resource(name, soft=soft)
        if soft and resource is None:
            return

        # Referential action
        if ref_action == 'restrict':
            # Check referencial-integrity
            path = str(resource.abspath)
            query = AndQuery(NotQuery(PhraseQuery('abspath', path)),
                             NotQuery(get_base_path_query(path)))
            sub_search = database.search(query)
            for sub_resource in resource.traverse_resources():
                path = str(sub_resource.abspath)
                query = PhraseQuery('links', path)
                results = sub_search.search(query)
                # A resource may have been updated in the same transaction,
                # so not yet reindexed: we need to check that the resource
                # really links.
                for referrer in results.get_resources():
                    if path in referrer.get_links():
                        err = 'cannot delete, resource "{}" is referenced'
                        raise ConsistencyError(err.format(path))
        elif ref_action == 'force':
            # Do not check referencial-integrity
            pass
        else:
            raise ValueError,('Incorrect ref_action "{}"'.format(ref_action))

        # Events, remove
        path = str(resource.abspath)
        database.remove_resource(resource)
        # Remove handlers
        for r in list(resource.traverse_resources()):
            for handler in [r.metadata] + r.get_fields_handlers():
                if database.has_handler(handler.key):
                    database.del_handler(handler.key)


    def _get_names(self):
        folder = self.handler
        for x in folder.get_handler_names():
            if x and x[-9:] == '.metadata':
                yield x[:-9]



    #######################################################################
    # API
    #######################################################################
    def _make_file(self, name, filename, mimetype, body, default_language):
        from webpage import WebPage

        if type(name) is not str:
            raise TypeError, 'expected string, got %s' % repr(name)

        # Web Pages are first class citizens
        if mimetype == 'text/html':
            body = tidy_html(body)
            class_id = 'webpage'
        elif mimetype == 'application/xhtml+xml':
            class_id = 'webpage'
        else:
            class_id = mimetype
        cls = self.database.get_resource_class(class_id)

        # Special case: web pages
        kw = {'filename': filename, 'data': body}
        if issubclass(cls, WebPage):
            kk, kk, language = FileName.decode(filename)
            if language is None:
                text = XHTMLFile(string=body).to_text()
                language = guess_language(text) or default_language
            kw['data'] = {language: body}

        return self.make_resource(name, cls, **kw)


    def export_zip(self, paths):
        stringio = StringIO()
        archive = ZipFile(stringio, mode='w')

        def _add_resource(resource):
            for filename in resource.get_files_to_archive(True):
                if filename.endswith('.metadata'):
                    continue
                path = Path(self.handler.key).get_pathto(filename)
                archive.writestr(str(path), resource.handler.to_str())

        for path in paths:
            child = self.get_resource(path, soft=True)
            if child is None:
                continue
            # A Folder => we add its content
            if isinstance(child, Folder):
                for subchild in child.traverse_resources():
                    if subchild is None or isinstance(subchild, Folder):
                        continue
                    _add_resource(subchild)
            else:
                _add_resource(child)

        archive.close()
        return stringio.getvalue()


    def extract_archive(self, handler, default_language, filter=None,
                        postproc=None, update=False):
        change_resource = self.database.change_resource
        for path_str in handler.get_contents():
            # 1. Skip folders
            clean_path = "/".join([
              checkid(x) or 'file'
              if x else 'file' for x in path_str.split("/")])
            path = Path(clean_path)
            if path.endswith_slash:
                continue

            # Skip the owner file (garbage produced by microsoft)
            filename = path[-1]
            if filename.startswith('~$'):
                continue

            # 2. Create parent folders if needed
            folder = self
            for name in path[:-1]:
                name, title = process_name(name)
                subfolder = folder.get_resource(name, soft=True)
                if subfolder is None:
                    folder = folder.make_resource(name, Folder)
                    folder.set_value('title', title, default_language)
                elif not isinstance(subfolder, Folder):
                    raise RuntimeError, MSG_NAME_CLASH
                else:
                    folder = subfolder

            # 3. Find out the resource name and title, the file mimetype and
            # language
            mimetype = guess_mimetype(filename, 'application/octet-stream')
            name, extension, language = FileName.decode(filename)
            name, title = process_name(name)
            language = language or default_language
            # Keep the filename extension (except in webpages)
            if mimetype not in ('application/xhtml+xml', 'text/html'):
                name = FileName.encode((name, extension, None))

            # 4. The body
            body = handler.get_file(path_str)
            if filter:
                body = filter(path_str, mimetype, body)
                if body is None:
                    continue

            # 5. Update or make file
            file = folder.get_resource(name, soft=True)
            if file:
                if update is False:
                    msg = 'unexpected resource at {path}'
                    raise RuntimeError, msg.format(path=path_str)
                if mimetype == 'text/html':
                    body = tidy_html(body)
                    file_handler = file.get_handler(language)
                else:
                    file_handler = file.get_handler()
                old_body = file.handler.to_str()
                file_handler.load_state_from_string(body)
                if postproc:
                    postproc(file)
                # FIXME Comparing the bytes does not work for XML, so we use
                # this weak heuristic
                if len(old_body) != len(file.handler.to_str()):
                    change_resource(file)
            else:
                # Case 1: the resource does not exist
                file = folder._make_file(name, filename, mimetype, body,
                                         language)
                file.set_value('title', title, language=language)
                if postproc:
                    postproc(file)


    def can_paste(self, source):
        """Is the source resource can be pasted into myself.
        """
        allowed_types = tuple(self.get_document_types())
        return isinstance(source, allowed_types)


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


    def copy_resource(self, source_path, target_path, exclude_patterns=None, check_if_authorized=True):
        # Find out the source and target absolute URIs
        source_path, target_path = self._resolve_source_target(source_path,
                                                               target_path)
        # Exclude patterns
        if exclude_patterns is None:
            exclude_patterns = []
        for exclude_pattern in exclude_patterns:
            if fnmatch.fnmatch(str(source_path), exclude_pattern):
                return
        # Get the source and target resources
        source = self.get_resource(source_path)
        childs = list(source.get_resources())
        parent_path = target_path.resolve2('..')
        target_parent = self.get_resource(parent_path)

        # Check compatibility
        if (check_if_authorized and
                (not target_parent.can_paste(source)
                 or not source.can_paste_into(target_parent))):
            message = u'resource type "{0}" cannot be copied into type "{1}"'
            message = message.format(source.class_title.gettext(),
                                     target_parent.class_title.gettext())
            raise ConsistencyError(message)

        # Copy the metadata
        folder = self.handler
        folder.copy_handler('%s.metadata' % source_path,
                            '%s.metadata' % target_path)

        # Copy the content
        database = self.database
        new_name = target_path.get_name()
        for old_name, new_name in source.rename_handlers(new_name):
            if old_name is None:
                continue
            src_key = Path(source_path).resolve(old_name)
            dst_key = Path(target_path).resolve(new_name)
            if folder.has_handler(src_key):
                folder.copy_handler(src_key, dst_key, exclude_patterns)
        # Events, add
        resource = self.get_resource(target_path)
        database.add_resource(resource)
        # Set ctime and mtime
        context = get_context()
        now = context.timestamp
        resource.set_uuid()
        resource.set_value('ctime', now)
        resource.set_value('mtime', now)
        # Childs
        for child in childs:
            source_path_child = source_path.resolve2(child.name)
            target_path_child = target_path.resolve2(child.name)
            self.copy_resource(source_path_child, target_path_child, exclude_patterns,
                check_if_authorized=False)
        # Ok
        return resource


    def move_resource(self, source_path, target_path, check_if_authorized=True):
        # Find out the source and target absolute URIs
        source_path, target_path = self._resolve_source_target(source_path,
                                                               target_path)

        # Get the source and target resources
        source = self.get_resource(source_path)
        parent_path = target_path.resolve2('..')
        target_parent = self.get_resource(parent_path)

        # Cannot move a resource to a subdirectory of itself
        abspath = self.abspath
        aux = source.abspath
        if aux.get_prefix(abspath) == aux:
            message = 'cannot move a resource to a subdirectory of itself'
            raise ConsistencyError, message

        # Check compatibility
        if (check_if_authorized and (not target_parent.can_paste(source)
                or not source.can_paste_into(target_parent))):
            message = 'resource type "%r" cannot be moved into type "%r"'
            raise ConsistencyError, message % (source, target_parent)

        # Events, remove
        database = self.database
        new_path = self.abspath.resolve2(target_path)
        database.move_resource(source, new_path)

        # Get childs
        childs = list(source.get_resources())

        # Move the metadata
        folder = self.handler
        folder.move_handler('%s.metadata' % source_path,
                            '%s.metadata' % target_path)
        # Move the content
        new_name = target_path.get_name()
        for old_name, new_name in source.rename_handlers(new_name):
            if old_name is None:
                continue
            src_key = Path(source_path).resolve(old_name)
            dst_key = Path(target_path).resolve(new_name)
            if folder.has_handler(src_key):
                folder.move_handler(src_key, dst_key)
        # Childs
        for child in childs:
            source_path_child = source_path.resolve2(child.name)
            target_path_child = target_path.resolve2(child.name)
            self.move_resource(source_path_child, target_path_child,
                check_if_authorized=False)



    def search_resources(self, cls=None, format=None):
        if cls is None:
            cls = DBResource

        for resource in self.get_resources():
            # Filter by base class
            if not isinstance(resource, cls):
                continue
            # Filter by class_id
            if format and resource.metadata.format != format:
                continue
            # All filters passed
            yield resource


    #######################################################################
    # User interface
    #######################################################################
    def get_view(self, name, query=None):
        # Add resource form
        if name == 'new_resource' and query:
            class_id = query.get('type')
            if class_id:
                cls = self.database.get_resource_class(class_id)
                view = cls.new_instance
                if is_prototype(view, BaseView):
                    context = get_context()
                    view = view(resource=self, context=context) # bind
                    # XXX Should we really check access here?
                    # Should raise forbidden, but callers are not ready.
                    root = context.root
                    user = context.user
                    if not root.has_permission(user, 'add', self, class_id):
                        return None
                    if not context.is_access_allowed(self, view):
                        return None
                    return view

        # Default
        return super(Folder, self).get_view(name, query)


    # Views
    view = Folder_BrowseContent()
    edit = AutoEdit(fields=['title', 'index', 'description', 'subject',
                            'share'])
    new_resource = Folder_NewResource()
    browse_content = Folder_BrowseContent()
    rename = Folder_Rename()
    preview_content = Folder_PreviewContent()
    thumb = Folder_Thumbnail()


###########################################################################
# Register
###########################################################################
Database.register_resource_class(Folder, 'application/x-not-regular-file')
