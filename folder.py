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
from itools.xapian import EqQuery, AndQuery, OrQuery, PhraseQuery

# Import from ikaaro
from base import DBObject, RedirectView
from datatypes import CopyCookie
from exceptions import ConsistencyError
from messages import *
from registry import register_object_class, get_object_class
from utils import generate_name
from views import IconsView, BrowseForm
import widgets
from workflow import WorkflowAware



###########################################################################
# Views
###########################################################################
class IndexView(RedirectView):

    access = True

    def GET(self, model, context):
        # Try index
        try:
            model.get_object('index')
        except LookupError:
            return RedirectView.GET(self, model, context)

        return context.uri.resolve2('index')


class AddView(IconsView):

    access = 'is_allowed_to_add'
    title = u'Add new content'
    icon = '/ui/icons/16x16/new.png'
    __label__ = MSG(u'Add', __name__)


    def get_namespace(self, model, context):
        items = [
            {
                'icon': '/ui/' + cls.class_icon48,
                'title': cls.class_title,
                'description': cls.class_description,
                'url': ';new_resource?type=%s' % quote(cls.class_id)
            }
            for cls in model.get_document_types() ]

        return {
            'title': MSG(u'Add new content', __name__),
            'batch': None,
            'items': items,
        }



class BrowseContent(BrowseForm):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    __label__ = MSG(u'Contents', __name__)
    title = u'Browse Content'
    icon = '/ui/icons/16x16/folder.png'

    schema = {
        'ids': String(multiple=True, mandatory=True),
    }

    search_fields =  [
        ('title', MSG(u'Title', __name__)),
        ('text', MSG(u'Text', __name__)),
        ('name', MSG(u'Name', __name__)),
    ]

    batchsize = 20


    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['title']),
        'batchstart': Integer(default=0),
    }


    def search_form(self, model, query):
        # Get values from the query
        field = query['search_field']
        term = query['search_term']

        # Build the namespace
        namespace = {}
        namespace['search_term'] = term
        namespace['search_fields'] = [
            {'name': name,
             'title': title,
             'selected': name == field}
            for name, title in self.search_fields ]

        # NOTE Folder's content specifics
        namespace['search_subfolders'] = query['search_subfolders']

        # Ok
        template = model.get_object('/ui/folder/browse_search.xml')
        return stl(template, namespace)


    def get_namespace(self, model, context, query, *args):
        # Get the parameters from the query
        search_term = query['search_term'].strip()
        field = query['search_field']
        sortby = query['sortby']
        sortorder = query['sortorder']
        search_subfolders = query['search_subfolders']

        # Build the query
        args = list(args)
        abspath = str(model.get_canonical_path())
        if search_subfolders is True:
            args.append(EqQuery('paths', abspath))
        else:
            args.append(EqQuery('parent_path', abspath))

        if search_term:
            args.append(PhraseQuery(field, search_term))

        if len(args) == 1:
            query = args[0]
        else:
            query = AndQuery(*args)

        # Build the namespace
        batchsize = self.batchsize
        namespace = model.browse_namespace(16, sortby, sortorder, batchsize,
                                           query=query)

        # The column headers
        columns = [
            ('name', MSG(u'Name', __name__)),
            ('title', MSG(u'Title', __name__)),
            ('format', MSG(u'Type', __name__)),
            ('mtime', MSG(u'Last Modified', __name__)),
            ('last_author', MSG(u'Last Author', __name__)),
            ('size', MSG(u'Size', __name__)),
            ('workflow_state', MSG(u'State', __name__))]

        # Actions
        user = context.user
        ac = model.get_access_control()
        actions = []
        if ac.is_allowed_to_edit(user, model):
            if namespace['total']:
                message = MSG_DELETE_SELECTION.gettext()
                actions = [
                    ('remove', MSG(u'Remove', __name__), 'button_delete',
                     'return confirmation("%s");' % message.encode('utf_8')),
                    ('rename', MSG(u'Rename', __name__), 'button_rename',
                     None),
                    ('copy', MSG(u'Copy', __name__), 'button_copy', None),
                    ('cut', MSG(u'Cut', __name__), 'button_cut', None)]
            if context.has_cookie('ikaaro_cp'):
                actions.append(
                    ('paste', MSG(u'Paste', __name__), 'button_paste', None))

        # Go!
        namespace['table'] = widgets.table(
            columns, namespace['objects'], sortby, sortorder, actions=actions)

        return namespace


    #######################################################################
    # Form Actions
    #######################################################################
    def remove(self, model, context, form):
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Remove objects
        removed = []
        not_removed = []
        user = context.user
        abspath = model.get_abspath()

        # We sort and reverse ids in order to
        # remove the childs then their parents
        ids.sort()
        ids.reverse()
        for name in ids:
            object = model.get_object(name)
            ac = object.get_access_control()
            if ac.is_allowed_to_remove(user, object):
                # Remove object
                try:
                    model.del_object(name)
                except ConsistencyError:
                    not_removed.append(name)
                    continue
                removed.append(name)
                # Clean cookie
                if str(abspath.resolve2(name)) in paths:
                    context.del_cookie('ikaaro_cp')
                    paths = []
            else:
                not_removed.append(name)

        objects = ', '.join(removed)
        context.message = MSG_OBJECTS_REMOVED.gettext(objects=objects)


    def rename(self, model, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = model.get_access_control()
        user = context.user
        paths = [ x for x in ids
                  if ac.is_allowed_to_move(user, model.get_object(x)) ]

        # Check input data
        if not paths:
            context.message = u'No objects selected.'
            return

        # FIXME Hack to get rename working. The current user interface forces
        # the rename_form to be called as a form action, hence with the POST
        # method, but it should be a GET method. Maybe it will be solved after
        # the needed folder browse overhaul.
        ids_list = '&'.join([ 'ids=%s' % x for x in paths ])
        return get_reference(';rename?%s' % ids_list)


    def copy(self, model, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to copy
        ac = model.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_copy(user, model.get_object(x)) ]

        # Check input data
        if not names:
            message = u'No objects selected.'
            return

        abspath = model.get_abspath()
        cp = (False, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')

        context.message = u'Objects copied.'


    def cut(self, model, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = model.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_move(user, model.get_object(x)) ]

        # Check input data
        if not names:
            message = u'No objects selected.'
            return

        abspath = model.get_abspath()
        cp = (True, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')

        context.message = u'Objects cut.'



class RenameForm(STLForm):

    access = 'is_allowed_to_edit'
    template = '/ui/folder/rename.xml'
    schema = {
        'paths': String(multiple=True, mandatory=True),
        'new_names': String(multiple=True, mandatory=True),
    }


    def get_namespace(self, model, context):
        ids = context.get_form_values('ids')
        # Filter names which the authenticated user is not allowed to move
        ac = model.get_access_control()
        user = context.user
        paths = [ x for x in ids
                  if ac.is_allowed_to_move(user, model.get_object(x)) ]

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


    def action(self, model, context, form):
        paths = form['paths']
        new_names = form['new_names']

        paths.sort()
        paths.reverse()
        # Clean the copy cookie if needed
        cut, cp_paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Process input data
        abspath = model.get_abspath()
        for i, path in enumerate(paths):
            new_name = new_names[i]
            new_name = checkid(new_name)
            if new_name is None:
                context.message = MSG_BAD_NAME
                return
            # Split the path
            if '/' in path:
                parent_path, old_name = path.rsplit('/', 1)
                container = model.get_object(parent_path)
            else:
                old_name = path
                container = model
            # Check the name really changed
            if new_name == old_name:
                continue
            # Check there is not another resource with the same name
            if container.has_object(new_name):
                context.message = MSG_EXISTANT_FILENAME
                return
            # Clean cookie (FIXME Do not clean the cookie, update it)
            if cp_paths and str(abspath.resolve2(path)) in cp_paths:
                context.del_cookie('ikaaro_cp')
                cp_paths = []
            # Rename
            container.move_object(old_name, new_name)

        message = u'Objects renamed.'
        return context.come_back(message, goto=';browse_content')



class PreviewView(STLView):

    access = 'is_allowed_to_view'
    __label__ = MSG(u'Contents', __name__)
    title = u'Preview Content'
    icon = '/ui/icons/16x16/image.png'
    template = '/ui/folder/browse_image.xml'

    search_fields =  [
        ('title', MSG(u'Title', __name__)),
        ('name', MSG(u'Name', __name__)),
    ]


    def get_namespace(self, model, context, search_subfolders=False, *args):
        # Get the form values
        get_form_value = context.get_form_value
        current_size = get_form_value('size', type=Integer,
                                      default=model.DEFAULT_SIZE)
        term = get_form_value('search_term', type=Unicode).strip()
        field = get_form_value('search_field')
        if field:
            search_subfolders = get_form_value('search_subfolders',
                                               type=Boolean, default=False)

        # Validate size
        current_size = max(model.MIN_SIZE, min(current_size, model.MAX_SIZE))

        # Compute previous and next sizes
        previous_size = model.MIN_SIZE
        next_size = model.MAX_SIZE
        for step in model.SIZE_STEPS:
            if step < current_size:
                previous_size = step
            if next_size is model.MAX_SIZE and step > current_size:
                next_size = step

        # Build the query
        args = list(args)
        args.append(EqQuery('is_image', '1'))
        abspath = str(model.get_canonical_path())
        if search_subfolders is True:
            args.append(EqQuery('paths', abspath))
        else:
            args.append(EqQuery('parent_path', abspath))

        if term:
            args.append(PhraseQuery(field, term))
        query = AndQuery(*args)

        # Build the namespace
        namespace = model.browse_namespace(16, batchsize=1000, query=query)
        namespace['search_term'] = term
        namespace['search_subfolders'] = search_subfolders
        namespace['search_fields'] = [
            {'id': name,
             'title': title,
             'selected': name == field or None}
            for name, title in self.search_fields ]
        namespace['size'] = current_size
        namespace['zoom_out'] = context.uri.replace(size=str(previous_size))
        namespace['zoom_in'] = context.uri.replace(size=str(next_size))

        # Append gallery style
        context.styles.append('/ui/gallery.css')
        return namespace


class LastChanges(BrowseContent):

    __label__ = MSG(u"Last Changes", __name__)
    title = u"Last Changes"
    icon = 'icalendar.png'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
        'sortorder': String(default='down'),
        'sortby': String(multiple=True, default=['mtime']),
        'batchstart': Integer(default=0),
    }



    def get_namespace(self, model, context, query):
        search_query = EqQuery('is_version_aware', '1')
        return BrowseContent.get_namespace(self, model, context, query,
                                           search_query)



class OrphansView(BrowseContent):
    """Orphans are files not referenced in another object of the database.  It
    extends the concept of "orphans pages" from the wiki to all file-like
    objects.

    Orphans folders generally don't make sense because they serve as
    containers. TODO or list empty folders?
    """

    access = 'is_allowed_to_view'
    __label__ = MSG(u"Orphans", __name__)
    title = u"Orphans"
    description = u"Show objects not linked from anywhere."
    icon = 'orphans.png'


    def get_namespace(self, model, context, sortby=['title'], sortorder='up',
                      batchsize=20):
        root = context.root
        get_form_value = context.get_form_value

        parent_path = str(model.get_canonical_path())
        search_subfolders = get_form_value('search_subfolders', type=Boolean,
                                           default=False)
        if search_subfolders is True:
            base_query = EqQuery('paths', parent_path)
            objects = model.traverse_objects()
        else:
            base_query = EqQuery('parent_path', parent_path)
            objects = model.get_objects()

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

        return BrowseContent.get_namespace(self, model, context, sortby,
               sortorder, batchsize, False, query)



###########################################################################
# Model
###########################################################################
class Folder(DBObject):

    class_id = 'folder'
    class_version = '20071215'
    class_layout = {}
    class_title = MSG(u'Folder', __name__)
    class_description = u'Organize your files and documents with folders.'
    class_icon16 = 'icons/16x16/folder.png'
    class_icon48 = 'icons/48x48/folder.png'
    class_views = [
        ['browse_content', 'preview_content'],
        ['new_resource'],
        ['edit_metadata']]
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
    def _has_object(self, name):
        folder = self.handler
        return folder.has_handler('%s.metadata' % name)


    def _get_names(self):
        folder = self.handler
        return [ x[:-9] for x in folder.get_handler_names()
                 if x[-9:] == '.metadata' ]


    def _get_object(self, name):
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


    def del_object(self, name):
        object = self.get_object(name)

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


    def copy_object(self, source, target):
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
        object = self.get_object(source)
        for old_name, new_name in object.rename_handlers(new_name):
            if old_name is None:
                continue
            src_uri = source_uri.resolve(old_name)
            dst_uri = target_uri.resolve(new_name)
            if folder.has_handler(src_uri):
                folder.copy_handler(src_uri, dst_uri)

        # Events, add
        object = self.get_object(target)
        context.server.add_object(object)


    def move_object(self, source, target):
        context = get_context()
        # Events, remove
        object = self.get_object(source)
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
        object = self.get_object(target)
        context.server.add_object(object)


    def traverse_objects(self):
        yield self
        for name in self._get_names():
            object = self.get_object(name)
            if isinstance(object, Folder):
                for x in object.traverse_objects():
                    yield x
            else:
                yield object


    def search_objects(self, path='.', format=None, state=None,
                       object_class=None):
        for object in self.get_objects(path):
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
            if state is not None and object.get_property('state') != state:
                continue
            # All filters passed
            yield object


    def get_human_size(self):
        names = self.get_names()
        size = len(names)

        return MSG(u'$n obs', __name__).gettext(n=size)


    #######################################################################
    # User interface
    #######################################################################
    def get_view(self, name, **kw):
        type = kw.get('type')
        if name == 'new_resource' and type is not None:
            cls = get_object_class(type)
            view = cls.new_instance
            if isinstance(view, BaseView):
                return view
#            raise ValueError, 'unknown type "%s"' % type
        return DBObject.get_view(self, name, **kw)


    def get_subviews(self, name):
        if name == 'new_resource':
            subviews = []
            for cls in self.get_document_types():
                id = cls.class_id
                ref = 'new_resource?type=%s' % quote_plus(id)
                subviews.append(ref)
            return subviews
        return DBObject.get_subviews(self, name)


    def get_context_menu_base(self):
        return self


    GET = IndexView()
    new_resource = AddView()
    browse_content = BrowseContent()
    rename = RenameForm()
    preview_content = PreviewView()
    last_changes = LastChanges()
    orphans = OrphansView()


    #######################################################################
    # Paste (FIXME)
    paste__access__ = 'is_allowed_to_edit'
    def paste(self, context):
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        if len(paths) == 0:
            message = MSG(u'Nothing to paste.', __name__)
            return context.come_back(message)

        root = context.root
        allowed_types = tuple(self.get_document_types())
        for path in paths:
            try:
                object = root.get_object(path)
            except LookupError:
                continue
            if not isinstance(object, allowed_types):
                continue

            # Cut&Paste in the same place (do nothing)
            if cut is True:
                parent = object.parent
                if self.get_canonical_path() == parent.get_canonical_path():
                    continue

            name = generate_name(object.name, self.get_names(), '_copy_')
            if cut is True:
                # Cut&Paste
                self.move_object(path, name)
            else:
                # Copy&Paste
                self.copy_object(path, name)
                # Fix state
                object = self.get_object(name)
                if isinstance(object, WorkflowAware):
                    metadata = object.metadata
                    metadata.set_property('state', object.workflow.initstate)
        # Cut, clean cookie
        if cut is True:
            context.del_cookie('ikaaro_cp')

        message = MSG(u'Objects pasted.', __name__)
        return context.come_back(message)



###########################################################################
# Register
###########################################################################
register_object_class(Folder)
register_object_class(Folder, format="application/x-not-regular-file")
