# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from urllib import quote
from datetime import datetime

# Import from the Python Image Library
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# Import from itools
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid, merge_dics
from itools.i18n import format_datetime
from itools.uri import get_reference, Path
from itools.web import BaseView, STLForm
from itools.xapian import AndQuery, EqQuery, OrQuery, PhraseQuery
from itools.xml import XMLParser

# Import from ikaaro
from datatypes import CopyCookie, ImageWidth
from exceptions import ConsistencyError
import messages
from resource_views import AddResourceMenu
from utils import generate_name
from versioning import VersioningAware
from views import IconsView, SearchForm, ContextMenu
from workflow import WorkflowAware



class ZoomMenu(ContextMenu):

    title = MSG(u'Zoom')

    def get_items(self, resource, context):
        uri = context.uri

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

        next_size = str(next_size)
        previous_size = str(previous_size)
        return [
            {'title': MSG(u'Zoom In'),
             'src': '/ui/icons/16x16/zoom_in.png',
             'href': uri.replace(size=next_size)},
            {'title': MSG(u'Zoom Out'),
             'src': '/ui/icons/16x16/zoom_out.png',
             'href': uri.replace(size=previous_size)}
        ]



class FolderView(BaseView):

    access = True

    def GET(self, resource, context):
        index = resource.get_resource('index')
        # FIXME We need to rewrite the URLs
        return index.view.GET(index, context)



class FolderNewResource(IconsView):

    access = 'is_allowed_to_add'
    title = MSG(u'Add resource')
    icon = 'new.png'


    def get_namespace(self, resource, context):
        items = [
            {'icon': '/ui/' + cls.class_icon48,
             'title': cls.class_title.gettext(),
             'description': cls.class_description.gettext(),
             'url': ';new_resource?type=%s' % quote(cls.class_id)
            }
            for cls in resource.get_document_types() ]

        return {
            'batch': None,
            'items': items}



class FolderRename(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Rename resources')
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
        items = []
        for path in paths:
            if '/' in path:
                parent_path, name = path.rsplit('/', 1)
                parent_path += '/'
            else:
                parent_path = ''
                name = path
            items.append({
                'path': path,
                'parent_path': parent_path,
                'name': name})

        return {'items': items}


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
                context.message = messages.MSG_BAD_NAME
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
                context.message = messages.MSG_EXISTANT_FILENAME
                return
            # Clean cookie (FIXME Do not clean the cookie, update it)
            if cp_paths and str(abspath.resolve2(path)) in cp_paths:
                context.del_cookie('ikaaro_cp')
                cp_paths = []
            # Rename
            container.move_resource(old_name, new_name)

        message = messages.MSG_RENAMED
        return context.come_back(message, goto=';browse_content')



class FolderBrowseContent(SearchForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Browse Content')
    context_menus = [AddResourceMenu()]
    schema = {
        'ids': String(multiple=True, mandatory=True),
    }

    # Search Form
    search_template = '/ui/folder/browse_search.xml'
    search_schema = {
        'search_field': String,
        'search_term': Unicode,
        'search_subfolders': Boolean(default=False),
    }

    # Table
    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('name', MSG(u'Name')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('size', MSG(u'Size')),
        ('workflow_state', MSG(u'State'))]


    def get_search_namespace(self, resource, context):
        namespace = SearchForm.get_search_namespace(self, resource, context)
        namespace['search_subfolders'] = context.query['search_subfolders']
        return namespace


    def get_items(self, resource, context, *args):
        # Get the parameters from the query
        query = context.query
        search_term = query['search_term'].strip()
        field = query['search_field']
        search_subfolders = query['search_subfolders']

        # Build the query
        args = list(args)
        abspath = str(resource.get_canonical_path())
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

        # Ok
        return context.root.search(query)


    def sort_and_batch(self, resource, context, results):
        start = context.query['batch_start']
        size = context.query['batch_size']
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        items = results.get_documents(sort_by=sort_by, reverse=reverse,
                                      start=start, size=size)

        # Access Control (FIXME this should be done before batch)
        user = context.user
        root = context.root
        allowed_items = []
        for item in items:
            item = root.get_resource(item.abspath)
            ac = item.get_access_control()
            if ac.is_allowed_to_view(user, item):
                allowed_items.append(item)

        return allowed_items


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            # checkbox
            parent = item.parent
            if parent is None:
                return None
            if item.name in parent.__fixed_handlers__:
                return None
            id = resource.get_canonical_path().get_pathto(item.get_abspath())
            id = str(id)
            return id, False
        elif column == 'icon':
            # icon
            path_to_icon = item.get_resource_icon(16)
            if path_to_icon.startswith(';'):
                path_to_icon = Path('%s/' % item.name).resolve(path_to_icon)
            return path_to_icon
        elif column == 'name':
            # Name
            id = resource.get_canonical_path().get_pathto(item.get_abspath())
            id = str(id)
            view = item.get_view(None)
            if view is None:
                return id
            href = '%s/' % id
            return id, href
        elif column == 'title':
            # Title
            return item.get_property('title')
        elif column == 'format':
            # Type
            return item.class_title.gettext()
        elif column == 'mtime':
            # Last Modified
            accept = context.accept_language
            return format_datetime(item.get_mtime(), accept=accept)
        elif column == 'last_author':
            # Last author
            if not isinstance(item, VersioningAware):
                return None
            revisions = item.get_revisions(context)
            if not revisions:
                return None
            username = revisions[0]['username']
            try:
                user = resource.get_resource('/users/%s' % username)
            except LookupError:
                return username
            return user.get_title()
        elif column == 'size':
            # Size
            return item.get_human_size()
        elif column == 'workflow_state':
            # The workflow state
            if not isinstance(item, WorkflowAware):
                return None
            statename = item.get_statename()
            state = item.get_state()
            msg = state['title'].gettext().encode('utf-8')
            # TODO Include the template in the base table
            state = ('<a href="%s/;edit_state" class="workflow">'
                     '<strong class="wf_%s">%s</strong>'
                     '</a>') % (resource.get_pathto(item), statename, msg)
            return XMLParser(state)


    def get_actions(self, resource, context, items):
        # Access Control
        ac = resource.get_access_control()
        if not ac.is_allowed_to_edit(context.user, resource):
            return []

        # Remove, Copy, Cut, Paste
        actions = []
        if len(items):
            message = messages.MSG_DELETE_SELECTION
            actions = [
                ('remove', MSG(u'Remove'), 'button_delete',
                 'return confirm("%s");' % message.gettext().encode('utf_8')),
                ('rename', MSG(u'Rename'), 'button_rename', None),
                ('copy', MSG(u'Copy'), 'button_copy', None),
                ('cut', MSG(u'Cut'), 'button_cut', None)]

        # Paste
        if context.has_cookie('ikaaro_cp'):
            actions.append(('paste', MSG(u'Paste'), 'button_paste', None))

        return actions


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)

        # Remove resources
        removed = []
        not_removed = []
        user = context.user
        abspath = resource.get_abspath()

        # We sort and reverse ids in order to
        # remove the childs then their parents
        ids.sort()
        ids.reverse()
        for name in ids:
            child = resource.get_resource(name)
            ac = child.get_access_control()
            if ac.is_allowed_to_remove(user, child):
                # Remove resource
                try:
                    resource.del_resource(name)
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

        if removed:
            resources = ', '.join(removed)
            message = messages.MSG_RESOURCES_REMOVED(resources=resources)
            context.message = message
        else:
            context.message = messages.MSG_NONE_REMOVED


    def action_rename(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        paths = [ x for x in ids
                  if ac.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not paths:
            context.message = messages.MSG_NONE_SELECTED
            return

        # FIXME Hack to get rename working. The current user interface forces
        # the rename_form to be called as a form action, hence with the POST
        # method, but it should be a GET method. Maybe it will be solved after
        # the needed folder browse overhaul.
        ids_list = '&'.join([ 'ids=%s' % x for x in paths ])
        return get_reference(';rename?%s' % ids_list)


    def action_copy(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to copy
        ac = resource.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_copy(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            message = messages.MSG_NONE_SELECTED
            return

        abspath = resource.get_abspath()
        cp = (False, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')
        # Ok
        context.message = messages.MSG_COPIED


    def action_cut(self, resource, context, form):
        ids = form['ids']
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        names = [ x for x in ids
                  if ac.is_allowed_to_move(user, resource.get_resource(x)) ]

        # Check input data
        if not names:
            context.message = messages.MSG_NONE_SELECTED
            return

        abspath = resource.get_abspath()
        cp = (True, [ str(abspath.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')

        context.message = messages.MSG_CUT


    action_paste_schema = {}
    def action_paste(self, resource, context, form):
        # Check there is something to paste
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        if len(paths) == 0:
            context.message = messages.MSG_NO_PASTE
            return

        # Paste
        target = resource
        allowed_types = tuple(target.get_document_types())
        for path in paths:
            # Check the resource actually exists
            try:
                resource = target.get_resource(path)
            except LookupError:
                continue
            if not isinstance(resource, allowed_types):
                continue

            # If cut&paste in the same place, do nothing
            if cut is True:
                source = resource.parent
                if target.get_canonical_path() == source.get_canonical_path():
                    continue

            name = generate_name(resource.name, target.get_names(), '_copy_')
            if cut is True:
                # Cut&Paste
                target.move_resource(path, name)
            else:
                # Copy&Paste
                target.copy_resource(path, name)
                # Fix state
                resource = target.get_resource(name)
                if isinstance(resource, WorkflowAware):
                    metadata = resource.metadata
                    metadata.set_property('state', resource.workflow.initstate)

        # Cut, clean cookie
        if cut is True:
            context.del_cookie('ikaaro_cp')

        context.message = messages.MSG_PASTED



class FolderPreviewContent(FolderBrowseContent):

    title = MSG(u'Preview Content')
    context_menus = FolderBrowseContent.context_menus + [ZoomMenu()]
    # Table
    table_template = '/ui/folder/browse_image.xml'


    def get_query_schema(self):
        # Define a huge batch limit, and the image size parameter
        return merge_dics(FolderBrowseContent.get_query_schema(self),
                          batch_size=Integer(default=0),
                          size=Integer(default=128),
                          width=String,
                          height=String)


    def get_items(self, resource, context):
        # Show only images
        query = OrQuery(EqQuery('is_image', '1'),
                        EqQuery('format', 'folder'))
        return FolderBrowseContent.get_items(self, resource, context, query)


    def get_actions(self, resource, context, items):
        actions = FolderBrowseContent.get_actions(self, resource, context,
                                                  items)
        if not actions:
            return []

        # Publish at once
        actions.append(('publish', MSG(u"Publish"), 'button_publish', None))

        return actions


    def get_table_namespace(self, resource, context, items):
        context.styles.append('/ui/gallery/style.css')
        context.scripts.append('/ui/gallery/javascript.js')

        # Get from the query
        query = context.query
        sort_by = query['sort_by']
        reverse = query['reverse']
        width = query['width']
        height = query['height']

        # (0) Zoom
        current_size = query['size']
        min_size = resource.MIN_SIZE
        max_size = resource.MAX_SIZE
        current_size = max(min_size, min(current_size, max_size))

        # (1) Actions (submit buttons)
        actions = self.get_actions(resource, context, items)
        actions = [{'name': name,
                    'value': value,
                    'class': cls,
                    'onclick': onclick}
                    for name, value, cls, onclick in actions ]

        # (2) Table Head: columns
        columns = self.get_table_columns(resource, context)
        columns_ns = []
        for name, title in columns:
            if name == 'checkbox':
                # Type: checkbox
                if  actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None:
                # Type: nothing
                continue
            else:
                # Type: normal
                kw = {'sort_by': name}
                if name == sort_by:
                    col_reverse = (not reverse)
                    order = 'up' if reverse else 'down'
                else:
                    col_reverse = False
                    order = 'none'
                kw['reverse'] = Boolean.encode(col_reverse)
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'order': order,
                    'href': context.uri.replace(**kw),
                    })

        # (3) Table Body: rows
        rows = []
        for item in items:
            row = {'checkbox': False,
                   # These are required for internal use
                   'title_or_name': item.get_title(),
                   'workflow_statename': None}
            # XXX Already hard-coded in the catalog search
            row['is_folder'] = (item.class_id == 'folder')
            if isinstance(item, WorkflowAware):
                row['workflow_statename'] = item.get_statename()
            for name, title in columns:
                value = self.get_item_value(resource, context, item, name)
                if value is None:
                    continue
                elif name == 'checkbox':
                    if actions:
                        value, checked = value
                        row['checkbox'] = True
                        row['id'] = value
                        row['checked'] = checked
                elif name == 'name':
                    if type(value) is tuple:
                        value, href = value
                        href = get_reference(href)
                        if row['is_folder']:
                            href = href.resolve2(';preview_content')
                        href = href.replace(size=current_size, width=width,
                                height=height)
                        href = str(href)
                    else:
                        href = None
                    row['name'] = value
                    row['href'] = href
                else:
                    row[name] = value
            rows.append(row)

        widths = ", ".join([str(o['name']) for o in ImageWidth.get_options()
                            if o['name'] is not None])

        return {'size': current_size,
                'width': width,
                'height': height,
                'widths': widths,
                'css': self.table_css,
                'columns': columns_ns,
                'rows': rows,
                'actions': actions}


    def action_publish(self, resource, context, form):
        resources = [resource.get_resource(id) for id in form['ids']]
        ac = resource.get_access_control()
        user = context.user
        transition = 'publish'
        allowed = [image for image in resources
                    if isinstance(image, WorkflowAware)
                    and ac.is_allowed_to_trans(user, image, transition)]

        if not allowed:
            context.message = messages.MSG_NONE_ALLOWED
            return

        for image in resources:
            if not isinstance(image, WorkflowAware):
                # A folder was selected
                continue
            if image.get_statename() == 'public':
                continue
            # Update workflow history
            property = {'date': datetime.now(),
                        'user': user.name,
                        'name': transition,
                        'comments': u""}
            image.set_property('wf_transition', property)
            image.do_trans(transition)

        context.message = messages.MSG_PUBLISHED



class FolderLastChanges(FolderBrowseContent):

    title = MSG(u"Last Changes")

    def get_query_schema(self):
        # Search subfolders by default
        return merge_dics(FolderBrowseContent.get_query_schema(self),
                          search_subfolders=Boolean(default=True))


    def get_items(self, resource, context):
        # Show only version aware resources
        query = EqQuery('is_version_aware', '1')
        return FolderBrowseContent.get_items(self, resource, context, query)



class FolderOrphans(FolderBrowseContent):
    """Orphans are files not referenced in another resource of the database.  It
    extends the concept of "orphans pages" from the wiki to all file-like
    resources.

    Orphans folders generally don't make sense because they serve as
    containers. TODO or list empty folders?
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Orphans")
    icon = 'orphans.png'
    description = MSG(u"Show resources not linked from anywhere.")


    def get_items(self, resource, context):
        # Make the base search
        items = FolderBrowseContent.get_items(self, resource, context)

        # Find out the orphans
        root = context.root
        orphans = []
        for item in items.get_documents():
            query = EqQuery('links', item.abspath)
            results = root.search(query)
            if len(results) == 0:
                orphans.append(item)

        # Transform back the items found in a SearchResults object.
        # FIXME This is required by 'get_item_value', we should change that,
        # for better performance.
        args = [ EqQuery('abspath', x.abspath) for x in orphans ]
        query = OrQuery(*args)
        items = root.search(query)

        # Ok
        return items



class FolderThumbnail(BaseView):

    access = True

    default_icon = '/ui/gallery/folder.png'

    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        from file import Image

        width = context.get_form_value('width', type=Integer, default=48)
        height = context.get_form_value('height', type=Integer, default=48)
        size = (width, height)
        data = None
        format = "jpeg"

        # Choose an image to illustrate
        default_icon = resource.get_resource(self.default_icon)
        if PILImage is None:
            # Full size but better than nothing
            data = default_icon.to_str()
            format = 'png'
        else:
            # Find the first accessible image
            user = context.user
            ac = resource.get_access_control()
            for image in resource.search_resources(cls=Image):
                # Search public image safe for all
                if ac.is_allowed_to_view(user, image):
                    data, format = image.handler.get_thumbnail(width, height)
                    break
            else:
                # Default icon for empty or inaccessible folders
                data, format = default_icon.get_thumbnail(width, height)

        # XXX Don't cache nothing here
        # The image thumbnail was cached in the image handler
        # The folder thumbnail was cached in the folder handler
        # Accessible images depend on too many parameters

        response = context.response
        response.set_header('Content-Type', 'image/%s' % format)
        return data
