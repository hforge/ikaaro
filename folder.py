# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
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
from urllib import quote, quote_plus

# Import from itools
from itools.datatypes import Boolean, DataType, Unicode, Integer, String
from itools.gettext import MSG
from itools.handlers import Folder as FolderHandler, checkid
from itools.stl import stl
from itools.uri import get_reference
from itools import vfs
from itools.web import get_context, BaseView, STLView, STLForm
from itools.xapian import EqQuery, AndQuery, OrQuery

# Import from ikaaro
from base import DBObject
from browse import BrowseContent
from datatypes import CopyCookie
from exceptions import ConsistencyError
from messages import *
from registry import register_object_class, get_object_class
from utils import generate_name
from views import IconsView
from widgets import build_menu
from workflow import WorkflowAware


###########################################################################
# Views
###########################################################################

class IndexView(BaseView):

    access = True

    def GET(self, resource, context):
        index = resource.get_resource('index')
        # FIXME We need to rewrite the URLs
        return index.view.GET(index, context)



class AddView(IconsView):

    access = 'is_allowed_to_add'
    title = MSG(u'Add resource')
    icon = 'new.png'


    def get_namespace(self, resource, context):
        items = [
            {
                'icon': '/ui/' + cls.class_icon48,
                'title': cls.class_title.gettext(),
                'description': cls.class_description.gettext(),
                'url': ';new_resource?type=%s' % quote(cls.class_id)
            }
            for cls in resource.get_document_types() ]

        return {
            'batch': None,
            'items': items,
        }



class RenameForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Rename objects')
    template = '/ui/folder/rename.xml'
    schema = {
        'paths': String(multiple=True, mandatory=True),
        'new_names': String(multiple=True, mandatory=True),
    }


    def get_namespace(self, resource, context):
        ids = context.get_form_values('ids')
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        paths = [ x for x in ids
                  if ac.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Build the namespace
        paths.sort()
        paths.reverse()
        objects = []
        for path in paths:
            if '/' in path:
                parent_path, name = path.rsplit('/', 1)
                parent_path += '/'
            else:
                parent_path = ''
                name = path
            objects.append({
                'path': path,
                'parent_path': parent_path,
                'name': name})

        return {'objects': objects}


    def action(self, resource, context, form):
        paths = form['paths']
        new_names = form['new_names']

        paths.sort()
        paths.reverse()
        # Clean the copy cookie if needed
        cut, cp_paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Process input data
        abspath = resource.get_abspath()
        for i, path in enumerate(paths):
            new_name = new_names[i]
            new_name = checkid(new_name)
            if new_name is None:
                context.message = MSG_BAD_NAME
                return
            # Split the path
            if '/' in path:
                parent_path, old_name = path.rsplit('/', 1)
                container = resource.get_resource(parent_path)
            else:
                old_name = path
                container = resource
            # Check the name really changed
            if new_name == old_name:
                continue
            # Check there is not another resource with the same name
            if container.has_resource(new_name):
                context.message = MSG_EXISTANT_FILENAME
                return
            # Clean cookie (FIXME Do not clean the cookie, update it)
            if cp_paths and str(abspath.resolve2(path)) in cp_paths:
                context.del_cookie('ikaaro_cp')
                cp_paths = []
            # Rename
            container.move_resource(old_name, new_name)

        message = MSG(u'Objects renamed.')
        return context.come_back(message, goto=';browse_content')



class PreviewView(BrowseContent):

    access = 'is_allowed_to_view'
    title = MSG(u'Preview Content')
    icon = 'image.png'

    batchsize = 1000

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['title']),
        'batchstart': Integer(default=0),
        'size': Integer(default=128),
    }


    def search(self, resource, context):
        query = EqQuery('is_image', '1')
        return BrowseContent.search(self, resource, context, query)


    def get_actions(self, resource, context, results):
        return []


    def get_table(self, resource, context, results):
        context.styles.append('/ui/gallery.css')

        # Zoom
        current_size = context.query['size']
        min_size = resource.MIN_SIZE
        max_size = resource.MAX_SIZE
        current_size = max(min_size, min(current_size, max_size))

        namespace = {
            'objects': self.get_rows(resource, context, results),
            'size': current_size,
        }

        template = resource.get_resource('/ui/folder/browse_image.xml')
        return stl(template, namespace)



class LastChanges(BrowseContent):

    title = MSG(u"Last Changes")
    icon = 'icalendar.png'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='down'),
        'sortby': String(multiple=True, default=['mtime']),
        'batchstart': Integer(default=0),
    }


    def get_namespace(self, resource, context):
        search_query = EqQuery('is_version_aware', '1')
        return BrowseContent.get_namespace(self, resource, context,
                                           search_query)



class OrphansView(BrowseContent):
    """Orphans are files not referenced in another object of the database.  It
    extends the concept of "orphans pages" from the wiki to all file-like
    objects.

    Orphans folders generally don't make sense because they serve as
    containers. TODO or list empty folders?
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Orphans")
    icon = 'orphans.png'
    description = MSG(u"Show objects not linked from anywhere.")


    def get_namespace(self, resource, context, sortby=['title'],
                      sortorder='up'):
        root = context.root
        get_form_value = context.get_form_value

        parent_path = str(resource.get_canonical_path())
        search_subfolders = get_form_value('search_subfolders', type=Boolean,
                                           default=False)
        if search_subfolders is True:
            base_query = EqQuery('paths', parent_path)
            objects = resource.traverse_objects()
        else:
            base_query = EqQuery('parent_path', parent_path)
            objects = resource.get_resources()

        orphans = []
        for object in objects:
            if isinstance(object, Folder):
                # TODO consider empty folders?
                continue
            abspath = str(object.get_abspath())
            query = AndQuery(base_query, EqQuery('links', abspath))
            results = root.search(query)
            if not results.get_n_documents():
                orphans.append(abspath)

        args = [ EqQuery('abspath', abspath) for abspath in orphans ]
        query = OrQuery(*args)

        return BrowseContent.get_namespace(self, resource, context, sortby,
               sortorder, False, query)



###########################################################################
# Model
###########################################################################
class Folder(DBObject):

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


    def traverse_objects(self):
        yield self
        for name in self._get_names():
            object = self.get_resource(name)
            if isinstance(object, Folder):
                for x in object.traverse_objects():
                    yield x
            else:
                yield object


    def search_objects(self, path='.', format=None, state=None,
                       object_class=None):
        for object in self.get_resources(path):
            if not isinstance(object, DBObject):
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

        return DBObject.get_default_view_name(self)


    def get_view(self, name, query=None):
        # Add resource form
        if name == 'new_resource':
            if query is not None and 'type' in query:
                view = get_object_class(query['type']).new_instance
                if isinstance(view, BaseView):
                    return view

        # Default
        return DBObject.get_view(self, name, query)


    def get_right_menus(self, context):
        menus = []
        if isinstance(context.view, PreviewView):
            resource = context.resource
            # Compute previous and next sizes
            current_size = context.query['size']
            min_size = resource.MIN_SIZE
            max_size = resource.MAX_SIZE
            current_size = max(min_size, min(current_size, max_size))
            previous_size = min_size
            next_size = max_size
            for step in resource.SIZE_STEPS:
                if step < current_size:
                    previous_size = step
                if next_size is max_size and step > current_size:
                    next_size = step

            options = [
                {'href': context.uri.replace(size=str(next_size)),
                 'src': '/ui/icons/16x16/zoom_in.png',
                 'title': MSG(u'Zoom In'),
                 'class': None,
                },
                {'href': context.uri.replace(size=str(previous_size)),
                 'src': '/ui/icons/16x16/zoom_out.png',
                 'title': MSG(u'Zoom Out'),
                 'class': None,
                }
            ]

            menus.append({
                'title': MSG(u'Zoom'),
                'content': build_menu(options)})

        # Ok
        return menus


    #######################################################################
    # Views
    view = IndexView()
    new_resource = AddView()
    browse_content = BrowseContent()
    rename = RenameForm()
    preview_content = PreviewView()
    last_changes = LastChanges()
    orphans = OrphansView()



###########################################################################
# Register
###########################################################################
register_object_class(Folder)
register_object_class(Folder, format="application/x-not-regular-file")
