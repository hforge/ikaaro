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
from itools.core import thingy_lazy_property
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import format_datetime
from itools.stl import set_prefix
from itools.uri import get_reference, Path
from itools.web import BaseView, STLView, STLForm, ERROR
from itools.web import boolean_field, input_field, integer_field
from itools.web import multiple_choice_field
from itools.xapian import AndQuery, OrQuery, PhraseQuery

# Import from ikaaro
from buttons import RemoveButton, RenameButton, CopyButton, CutButton
from buttons import PasteButton, PublishButton, RetireButton
from datatypes import CopyCookie
from exceptions import ConsistencyError
from fields import image_size_field
from globals import ui
import messages
from utils import generate_name
from views import IconsView, SearchForm, ContextMenu
from workflow import WorkflowAware, get_workflow_preview



class ZoomMenu(ContextMenu):

    title = MSG(u'Zoom')
    size_steps = ('64x64', '128x128', '256x256', '512x512')


    def get_items(self):
        current_size = self.context.query.get('image_size')

        uri = get_reference(self.context.uri)
        return  [
            {'href': uri.replace(image_size=x), 'title': x,
             'class': 'nav-active' if x == current_size else None}
            for x in self.size_steps ]



class Folder_View(BaseView):

    access = 'is_allowed_to_view_folder'
    view_title = MSG(u'View')


    def http_get(self):
        index = self.resource.get_resource('index', soft=True)
        if index is None:
            context = self.context
            context.message = ERROR(
                u'There is not an "index" web page. Could not render this '
                u'view.')
            return context.ok_wrap('text/html', '')

        # Rewrite the URLs
        stream = index.get_html_data()
        return set_prefix(stream, 'index/')



class Folder_List(STLView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'List View')
    template = 'folder/list.xml'


    def items(self):
        context = self.context
        search = context.get_root_search(self.resource.path)
        items = []
        for resource in search.get_documents(sort_by='mtime', reverse=True):
            mtime = resource.get_value('mtime')
            items.append({
                'href': resource.path,
                'title': resource.get_title(),
                'date': format_datetime(mtime),
                'description': resource.get_value('description')})
        return items



class Folder_NewResource(IconsView):

    access = 'is_allowed_to_add'
    view_title = MSG(u'Add resource')
    icon = 'new.png'


    batch = None

    def items(self):
        return [
            {'icon': '/ui/' + x.class_icon48,
             'title': x.class_title.gettext(),
             'description': x.class_description.gettext(),
             'url': ';new_resource?type=%s' % quote(x.class_id)}
            for x in self.resource.get_document_types() ]



class Folder_Rename(STLForm):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Rename resources')
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
        return context.come_back(message, goto=';table')



class Folder_Table(SearchForm):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Table View')
    context_menus = []

    # Schema
    ids = multiple_choice_field(required=True)
    sort_by = SearchForm.sort_by(value='mtime')
    reverse = SearchForm.reverse(value=True)

    # Table
    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('name', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('format', MSG(u'Type')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('size', MSG(u'Size')),
        ('workflow_state', MSG(u'State'))]


    def get_base_query(self):
        return []


    @thingy_lazy_property
    def all_items(self):
        resource = self.resource
        context = self.context

        # The query
        args = self.get_base_query()
        search_term = self.search_term.value
        if search_term:
            search_fields = ['title', 'text', 'name']
            query = [ PhraseQuery(x, search_term) for x in search_fields ]
            query = OrQuery(*query)
            args.append(query)

        results = context.get_root_search(resource.path, False)
        if len(args) == 0:
            return results

        if len(args) == 1:
            query = args[0]
        else:
            query = AndQuery(*args)
        return results.search(query)


    @thingy_lazy_property
    def items(self):
        start = self.batch_start.value
        size = self.batch_size.value
        sort_by = self.sort_by.value
        reverse = self.reverse.value
        items = self.all_items
        resources = items.get_documents(sort_by=sort_by, reverse=reverse,
                                        start=start, size=size)

        # Sort the title by lower case (FIXME should be done by the catalog)
        if sort_by == 'title':
            key = lambda x: x.get_value('title').lower()
            resources = sorted(resources, key=key, reverse=reverse)

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
    def action_remove(self):
        # Clean the copy cookie if needed
        context = self.context
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)

        # Remove resources
        removed = []
        referenced = []
        not_removed = []
        user = context.user

        # We sort and reverse ids in order to
        # remove the childs then their parents
        resource = self.resource
        ids = sorted(self.ids.value, reverse=True)
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



class Folder_Gallery(Folder_Table):

    view_title = MSG(u'Gallery')
    styles = ['/ui/gallery/style.css']
    scripts = ['/ui/gallery/javascript.js']

    context_menus = Folder_Table.context_menus + [ZoomMenu()]
    # Table
    table_template = 'folder/browse_image.xml'

    # no batch
    batch_size = Folder_Table.batch_size()
    batch_size.datatype = Integer(value=0)

    image_size = image_size_field(source='query', width=128, height=128)


    def get_base_query(self):
        # Show only images
        query = OrQuery(PhraseQuery('is_image', True),
                        PhraseQuery('format', 'folder'))
        return [query]


    def columns(self):
        # Get from the query
        sort_by = self.sort_by.value
        reverse = self.reverse.value

        columns = self._get_table_columns()
        columns_ns = []
        uri = get_reference(self.context.uri)
        for name, title, sortable in columns:
            if name == 'checkbox':
                # Type: checkbox
                if self.external_form or self.actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None:
                continue
            elif not sortable:
                # Type: nothing or not sortable
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'href': None,
                    'sortable': False})
            else:
                # Type: normal
                base_href = uri.replace(sort_by=name)
                if name == sort_by:
                    sort_up_active = reverse is False
                    sort_down_active = reverse is True
                else:
                    sort_up_active = sort_down_active = False
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'sortable': True,
                    'href': uri.path,
                    'href_up': base_href.replace(reverse=0),
                    'href_down': base_href.replace(reverse=1),
                    'sort_up_active': sort_up_active,
                    'sort_down_active': sort_down_active})
        return columns_ns


    def rows(self):
        image_size = self.image_size.encoded_value

        columns = self._get_table_columns()
        rows = []
        for item in self.items:
            row = {'checkbox': False,
                   # These are required for internal use
                   'title_or_name': item.get_value('title'),
                   'workflow_statename': None}
            # XXX Already hard-coded in the catalog search
            row['is_folder'] = (item.class_id == 'folder')
            if isinstance(item, WorkflowAware):
                row['workflow_statename'] = item.get_statename()
            for name, title, sortable in columns:
                value = self.get_item_value(item, name)
                if value is None:
                    continue
                elif name == 'checkbox':
                    if self.actions:
                        value, checked = value
                        row['checkbox'] = True
                        row['id'] = value
                        row['checked'] = checked
                elif name == 'name':
                    if type(value) is tuple:
                        value, href = value
                        href = get_reference(href)
                        if row['is_folder']:
                            href = href.resolve_name(';gallery')
                        href = href.replace(image_size=image_size)
                        href = str(href)
                    else:
                        href = None
                    row['name'] = value
                    row['href'] = href
                else:
                    row[name] = value
            rows.append(row)

        return rows


    def root(self):
        return self.resource.path == '/'


    def widths(self):
        # FIXME hardcoded
        sizes = ['640x480', '800x600', '1024x768', '1280x1024']
        return ", ".join(sizes)



class Folder_Orphans(Folder_Table):
    """Orphans are files not referenced in another resource of the database.
    It extends the concept of "orphans pages" from the wiki to all file-like
    resources.

    Orphans folders generally don't make sense because they serve as
    containers. TODO or list empty folders?
    """

    access = 'is_allowed_to_view'
    view_title = MSG(u"Orphans")
    icon = 'orphans.png'
    description = MSG(u"Show resources not linked from anywhere.")


    @thingy_lazy_property
    def all_items(self):
        # Make the base search
        items = Folder_Table.get_items(self, resource, context)

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

    width = integer_field(source='query', value=48)
    height = integer_field(source='query', value=48)


    def get_mtime(self, resource):
        return resource.get_mtime()


    def http_get(self):
        from file import Image

        context = self.context
        width = self.width.value
        height = self.height.value

        # Choose an image to illustrate
        if PILImage is None:
            # Full size but better than nothing
            default_icon = ui.get_template(self.default_icon)
            data = default_icon.to_str()
            format = 'png'
        else:
            # Find the first accessible image
            user = context.user
            resource = self.resource
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
    view_title = MSG(u'Front Page')
    icon = 'view.png'
    specific_document = 'FrontPage'


    def get_specific_document(self, resource, context):
        return self.specific_document


    def http_get(self):
        specific_document = self.get_specific_document(resource, context)
        goto = '%s/%s' % (context.get_link(resource), specific_document)
        goto = get_reference(goto)

        # Keep the message
        if context.has_form_value('message'):
            message = context.get_form_value('message')
            goto = goto.replace(message=message)

        return goto

