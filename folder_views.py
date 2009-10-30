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

# Import from the Python Image Library
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# Import from itools
from itools.core import merge_dicts, thingy_lazy_property
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import format_datetime
from itools.stl import set_prefix
from itools.uri import get_reference, Path
from itools.web import BaseView, STLForm, ERROR, ViewField
from itools.xapian import AndQuery, OrQuery, PhraseQuery

# Import from ikaaro
from buttons import RemoveButton, RenameButton, CopyButton, CutButton
from buttons import PasteButton, PublishButton, RetireButton
from datatypes import CopyCookie, ImageWidth
from exceptions import ConsistencyError
from globals import ui
import messages
from utils import generate_name
from views import IconsView, SearchForm, ContextMenu
from workflow import WorkflowAware, get_workflow_preview



class ZoomMenu(ContextMenu):

    title = MSG(u'Zoom')

    def get_items(self):
        uri = get_reference(self.context.uri)

        # Compute previous and next sizes
        current_size = self.context.get_query_value('size')
        min_size = self.resource.MIN_SIZE
        max_size = self.resource.MAX_SIZE
        current_size = max(min_size, min(current_size, max_size))
        previous_size = min_size
        next_size = max_size
        for step in self.resource.SIZE_STEPS:
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
             'href': uri.replace(size=previous_size)}]



class Folder_View(BaseView):

    access = 'is_allowed_to_view_folder'
    title = MSG(u'View')


    def http_get(self):
        from webpage import WebPage

        index = self.resource.get_resource('index', soft=True)
        if not isinstance(index, WebPage):
            context = self.context
            context.message = ERROR(
                u'There is not an "index" web page. Could not render this '
                u'view.')
            return context.ok_wrap('text/html', '')

        # Rewrite the URLs
        stream = index.get_html_data()
        return set_prefix(stream, 'index/')



class Folder_NewResource(IconsView):

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



class Folder_Rename(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Rename resources')
    template = 'folder/rename.xml'
    query_schema = {
        'ids': String(multiple=True)}
    schema = {
        'paths': String(multiple=True, mandatory=True),
        'new_names': String(multiple=True, mandatory=True)}


    def get_namespace(self, resource, context):
        ids = context.get_query_value('ids')
        # Filter names which the authenticated user is not allowed to move
        ac = resource.get_access_control()
        user = context.user
        paths = []
        for name in ids:
            r = resource.get_resource(name, soft=True)
            if r and ac.is_allowed_to_move(user, r):
                paths.append(name)

        # Build the namespace
        paths.sort(reverse=True)
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
        cut, cp_paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)

        renamed = []
        referenced = []
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
            if container.get_resource(new_name, soft=True) is not None:
                context.message = messages.MSG_EXISTANT_FILENAME
                return
            # Clean cookie (FIXME Do not clean the cookie, update it)
            if cp_paths and str(abspath.resolve2(path)) in cp_paths:
                context.del_cookie('ikaaro_cp')
                cp_paths = []
            # Rename
            try:
                container.move_resource(old_name, new_name)
            except ConsistencyError:
                referenced.append(old_name)
                continue
            else:
                renamed.append(old_name)

        if referenced and not renamed:
            resources = ', '.join(referenced)
            message = messages.MSG_RESOURCES_REFERENCED(resources=resources)
        else:
            message = messages.MSG_RENAMED
        return context.come_back(message, goto=';browse_content')



class Folder_BrowseContent(SearchForm):

    access = 'is_allowed_to_view'
    title = MSG(u'Browse Content')
    context_menus = []

    # Search Form
    search_template = 'folder/browse_search.xml'

    # Schema
    ids = ViewField(required=True)
    ids.datatype = String(multiple=True)
    sort_by = SearchForm.sort_by(default='mtime')
    reverse = SearchForm.reverse(default=True)
    search_subfolders = ViewField(source='query')
    search_subfolders.datatype = Boolean(default=False)

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


    @thingy_lazy_property
    def all_items(self):
        resource = self.resource
        context = self.context

        # The query
        args = []
        search_term = self.search_term.value
        if search_term:
            field = self.search_field.value
            args.append(PhraseQuery(field, search_term))

        # Case 1: search subfolders
        search_subfolders = self.search_subfolders.value
        if search_subfolders is True:
            results = context.get_root_search(resource.path, False)
            if len(args) == 0:
                query = None
            elif len(args) == 1:
                query = args[0]
            else:
                query = AndQuery(*args)
            return results.search(query)

        # Case 2: do not search subfolders
        path = resource.get_physical_path()
        path = str(path)
        parent_query = PhraseQuery('parent_path', path)
        query = AndQuery(parent_query, *args) if args else parent_query
        return context.search(query)


    @thingy_lazy_property
    def items(self):
        start = self.batch_start.value
        size = self.batch_size.value
        sort_by = self.sort_by.value
        reverse = self.reverse.value
        items = self.all_items
        resources = items.get_documents(sort_by=sort_by, reverse=reverse,
                                        start=start, size=size)

        # FIXME This must be done in the catalog
        if sort_by == 'title':
            resources = sorted(resources, key=lambda x: x.get_value('title'))
            if reverse:
                resources.reverse()

        # Access Control (FIXME this should be done before batch)
        user = self.context.user
        allowed_items = []
        for resource in resources:
            ac = resource.get_access_control()
            if ac.is_allowed_to_view(user, resource):
                allowed_items.append(resource)

        return allowed_items


    def get_item_value(self, item, column):
        if column == 'checkbox':
            # checkbox
            parent = item.get_parent()
            if parent is None:
                return None
            if item.get_name() in parent.__fixed_handlers__:
                return None
            id = self.resource.path.get_pathto(item.path)
            id = str(id)
            return id, False
        elif column == 'icon':
            # icon
            path_to_icon = item.get_resource_icon(16)
            if path_to_icon.startswith(';'):
                name = item.get_name()
                path_to_icon = Path('%s/' % name).resolve(path_to_icon)
            return path_to_icon
        elif column == 'name':
            # Name
            id = self.resource.path.get_pathto(item.path)
            id = str(id)
            view = item.get_view(None)
            if view is None:
                return id
            href = '%s/' % item.path
            return id, href
        elif column == 'title':
            # Title
            return item.get_value('title')
        elif column == 'format':
            # Type
            return item.class_title.gettext()
        elif column == 'mtime':
            # Last Modified
            accept = self.context.accept_language
            return format_datetime(item.get_value('mtime'), accept=accept)
        elif column == 'last_author':
            # Last author
            return self.context.get_user_title(item.get_value('last_author'))
        elif column == 'size':
            # Size
            return item.get_human_size()
        elif column == 'workflow_state':
            # The workflow state
            return get_workflow_preview(item, self.context)


    table_actions = [
        RemoveButton, RenameButton, CopyButton, CutButton, PasteButton,
        PublishButton, RetireButton]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)

        # Remove resources
        removed = []
        referenced = []
        not_removed = []
        user = context.user

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
                    referenced.append(name)
                    continue
                removed.append(name)
                # Clean cookie
                if str(resource.path.resolve2(name)) in paths:
                    context.del_cookie('ikaaro_cp')
                    paths = []
            else:
                not_removed.append(name)

        message = []
        if removed:
            resources = ', '.join(removed)
            msg = messages.MSG_RESOURCES_REMOVED(resources=resources)
            message.append(msg)
        if referenced:
            resources = ', '.join(referenced)
            msg = messages.MSG_RESOURCES_REFERENCED(resources=resources)
            message.append(msg)
        if not_removed:
            resources = ', '.join(not_removed)
            msg = messages.MSG_RESOURCES_NOT_REMOVED(resources=resources)
            message.append(msg)
        if not removed and not referenced and not not_removed:
            message.append(messages.MSG_NONE_REMOVED)
        context.message = message
        context.redirect()


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
        context.query['ids'] = paths
        context.redirect(view='rename')


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

        path = resource.path
        cp = (False, [ str(path.resolve2(x)) for x in names ])
        cp = CopyCookie.encode(cp)
        context.set_cookie('ikaaro_cp', cp, path='/')
        # Ok
        context.message = messages.MSG_COPIED
        context.redirect()


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
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        if len(paths) == 0:
            context.message = messages.MSG_NO_PASTE
            return

        # Paste
        target = resource
        pasted = []
        not_allowed = []
        for path in paths:
            # Check the source resource still exists
            source = target.get_resource(path, soft=True)
            if source is None:
                continue

            # If cut&paste in the same place, do nothing
            name = source.get_name()
            if cut is True:
                if target == source.get_parent():
                    pasted.append(name)
                    continue

            name = generate_name(name, target.get_names(), '_copy_')
            if cut is True:
                # Cut&Paste
                try:
                    target.move_resource(path, name)
                except ConsistencyError:
                    not_allowed.append(source.get_name())
                    continue
                else:
                    pasted.append(name)
            else:
                # Copy&Paste
                try:
                    target.copy_resource(path, name)
                except ConsistencyError:
                    not_allowed.append(source.get_name())
                    continue
                else:
                    pasted.append(name)
                    # Fix state
                    copy = target.get_resource(name)
                    if isinstance(copy, WorkflowAware):
                        metadata = copy.metadata
                        metadata.set_property('state',
                                              copy.workflow.initstate)

        # Cut, clean cookie
        if cut is True:
            context.del_cookie('ikaaro_cp')

        message = []
        if pasted:
            resources = ', '.join(pasted)
            message.append(messages.MSG_RESOURCES_PASTED(resources=resources))
        if not_allowed:
            resources = ', '.join(not_allowed)
            msg = messages.MSG_RESOURCES_NOT_PASTED(resources=resources)
            message.append(msg)

        context.message = message
        context.redirect()


    def _action_workflow(self, resource, context, form, transition, statename,
                         message):
        resources = [ resource.get_resource(id) for id in form['ids'] ]
        user = context.user
        # Check there is at least one item we can publish
        ac = resource.get_access_control()
        allowed = [ x for x in resources
                    if ac.is_allowed_to_trans(user, x, transition) ]
        if not allowed:
            context.message = messages.MSG_NONE_ALLOWED
            return

        # Publish
        for item in allowed:
            if item.get_statename() == statename:
                continue
            # Update workflow history
            item.make_transition(transition)

        # Ok
        context.message = message


    def action_publish(self, resource, context, form):
        self._action_workflow(resource, context, form, 'publish', 'public',
                              messages.MSG_PUBLISHED)


    def action_retire(self, resource, context, form):
        self._action_workflow(resource, context, form, 'retire', 'private',
                              messages.MSG_RETIRED)



class Folder_PreviewContent(Folder_BrowseContent):

    title = MSG(u'Preview Content')
    styles = ['/ui/gallery/style.css']
    scripts = ['/ui/gallery/javascript.js']

    context_menus = Folder_BrowseContent.context_menus + [ZoomMenu()]
    # Table
    table_template = 'folder/browse_image.xml'


    def get_query_schema(self):
        # Define a huge batch limit, and the image size parameter
        return merge_dicts(Folder_BrowseContent.get_query_schema(self),
                           batch_size=Integer(default=0),
                           size=Integer(default=128),
                           width=String,
                           height=String)


    @thingy_lazy_property
    def all_items(self):
        # Show only images
        query = OrQuery(PhraseQuery('is_image', True),
                        PhraseQuery('format', 'folder'))
        return Folder_BrowseContent.get_items(self, resource, context, query)


    def get_table_head(self, items, actions=None):
        # Get from the query
        sort_by = context.get_query_value('sort_by')
        reverse = context.get_query_value('reverse')

        columns = self._get_table_columns()
        columns_ns = []
        uri = get_reference(context.uri)
        for name, title, sortable in columns:
            if name == 'checkbox':
                # Type: checkbox
                if  actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None:
                # Type: nothing
                continue
            elif not sortable:
                # Type: nothing or not sortable
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'href': None})
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
                    'href': uri.replace(**kw)})


    def get_table_namespace(self, resource, context, items):
        # Get from the query
        width = context.get_query_value('width')
        height = context.get_query_value('height')

        # (0) Zoom
        current_size = context.get_query_value('size')
        min_size = resource.MIN_SIZE
        max_size = resource.MAX_SIZE
        current_size = max(min_size, min(current_size, max_size))

        # (1) Actions (submit buttons)
        ac = resource.get_access_control()
        actions = []
        for button in self.table_actions:
            if button.show(resource, context, items) is False:
                continue
            if button.confirm:
                confirm = button.confirm.gettext().encode('utf_8')
                onclick = 'return confirm("%s");' % confirm
            else:
                onclick = None
            actions.append(
                {'value': button.name,
                 'title': button.title,
                 'class': button.css,
                 'onclick': onclick})

        # (2) Table Head: columns
        table_head = self.get_table_head(resource, context, items, actions)

        # (3) Table Body: rows
        columns = self._get_table_columns()
        rows = []
        for item in items:
            row = {'checkbox': False,
                   # These are required for internal use
                   'title_or_name': item.get_value('title'),
                   'workflow_statename': None}
            # XXX Already hard-coded in the catalog search
            row['is_folder'] = (item.class_id == 'folder')
            if isinstance(item, WorkflowAware):
                row['workflow_statename'] = item.get_statename()
            for name, title, sortable in columns:
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
                            href = href.resolve_name(';preview_content')
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

        widths = ", ".join([repr(o['name']) for o in ImageWidth.get_options()
                            if o['name'].strip()])

        return {
            'root': resource.get_parent() is None,
            'size': current_size,
            'width': width,
            'height': height,
            'widths': widths,
            'css': self.table_css,
            'columns': table_head,
            'rows': rows,
            'actions': actions}




class Folder_Orphans(Folder_BrowseContent):
    """Orphans are files not referenced in another resource of the database.
    It extends the concept of "orphans pages" from the wiki to all file-like
    resources.

    Orphans folders generally don't make sense because they serve as
    containers. TODO or list empty folders?
    """

    access = 'is_allowed_to_view'
    title = MSG(u"Orphans")
    icon = 'orphans.png'
    description = MSG(u"Show resources not linked from anywhere.")


    @thingy_lazy_property
    def all_items(self):
        # Make the base search
        items = Folder_BrowseContent.get_items(self, resource, context)

        # Find out the orphans
        orphans = []
        for item in items.get_documents():
            query = PhraseQuery('links', item.abspath)
            results = context.search(query)
            if len(results) == 0:
                orphans.append(item)

        # Transform back the items found in a SearchResults object.
        # FIXME This is required by 'get_item_value', we should change that,
        # for better performance.
        args = [ PhraseQuery('abspath', x.abspath) for x in orphans ]
        query = OrQuery(*args)
        items = context.search(query)

        # Ok
        return items



class Folder_Thumbnail(BaseView):

    access = True

    default_icon = 'gallery/folder.png'

    def http_get(self):
        from file import Image

        width = context.get_query_value('width', type=Integer, default=48)
        height = context.get_query_value('height', type=Integer, default=48)

        # Choose an image to illustrate
        if PILImage is None:
            # Full size but better than nothing
            default_icon = ui.get_template(self.default_icon)
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
                default_icon = ui.get_template(self.default_icon)
                data, format = default_icon.get_thumbnail(width, height)

        # XXX Cache nothing here
        # The image thumbnail was cached in the image handler
        # The folder thumbnail was cached in the folder handler
        # Accessible images depend on too many parameters
        context.ok('image/%s' % format, data)



class GoToSpecificDocument(BaseView):

    access = 'is_allowed_to_view'
    title = MSG(u'Front Page')
    icon = 'view.png'
    specific_document = 'FrontPage'


    def get_specific_document(self, resource, context):
        return self.specific_document


    def http_get(self):
        specific_document = self.get_specific_document(resource, context)
        goto = '%s/%s' % (context.get_link(resource), specific_document)
        goto = get_reference(goto)

        # Keep the message
        message = context.get_form_value('message')
        if message:
            goto = goto.replace(message=message)

        return goto

