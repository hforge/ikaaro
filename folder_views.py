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
from itools.core import freeze, thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import format_datetime
from itools.stl import set_prefix
from itools.uri import get_reference, Path
from itools.web import view, stl_view, ERROR
from itools.web import boolean_field, input_field, integer_field
from itools.web import multiple_choice_field
from itools.web import make_stl_template
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
from views import IconsView, ContextMenu
from views import Container_Search, Container_Sort, Container_Batch
from views import Container_Form, Container_Table



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



class Folder_View(view):

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


class Folder_Search(Container_Search):

    base_query = None

    search_fields = freeze(['title', 'text', 'name'])

    @thingy_lazy_property
    def items(self):
        # Base search
        results = self.context.get_root_search(self.resource.path, False)
        if self.base_query:
            results = results.search(self.base_query)

        # Case 1: no query
        search_term = self.term.value
        if not search_term:
            return results

        # Case 2: query
        query = [ PhraseQuery(x, search_term) for x in self.search_fields ]
        query = OrQuery(*query)
        return results.search(query)


class Folder_Sort(Container_Sort):

    sort_by = Container_Sort.sort_by()
    sort_by.value = 'mtime'
    sort_by.values = OrderedDict([
        ('name', {'title': MSG(u'Path')}),
        ('title', {'title': MSG(u'Title')}),
        ('format', {'title': MSG(u'Type')}),
        ('mtime', {'title': MSG(u'Last Modified')}),
        ('last_author', {'title': MSG(u'Last Author')}),
        ('workflow_state', {'title': MSG(u'State')})])


    reverse = Container_Sort.reverse(value=True)



class Folder_Batch(Container_Batch):

    @thingy_lazy_property
    def items(self):
        start = self.batch_start.value
        size = self.batch_size.value
        sort_by = self.view.sort.sort_by.value
        reverse = self.view.sort.reverse.value
        items = self.view.search.items
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
            ac = resource.access_control
            if ac.is_allowed_to_view(user, resource):
                allowed_items.append(resource)

        return allowed_items



class Folder_List(stl_view):

    access = 'is_allowed_to_view'
    view_title = MSG(u'List View')
    template = 'folder/list.xml'

    search = Folder_Search()

    def items(self):
        all_items = self.search.items

        context = self.context
        search = context.get_root_search(self.resource.path)
        items = []
        for resource in all_items.get_documents(sort_by='mtime', reverse=True):
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



class Folder_Rename(stl_view):

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
        ac = resource.access_control
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



class Folder_Table(stl_view):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Table View')
    context_menus = []

    template = make_stl_template("${search}${batch}${form}")

    # Search, Sort, Batch
    search = Folder_Search()
    sort = Folder_Sort()
    batch = Folder_Batch()

    # Form
    form = Container_Form()

    # Table
    form.content = Container_Table()
    form.content.header = [
        ('checkbox', None, False),
        ('icon', None, False),
        ('name', MSG(u'Path'), True),
        ('title', MSG(u'Title'), True),
        ('format', MSG(u'Type'), True),
        ('mtime', MSG(u'Last Modified'), True),
        ('last_author', MSG(u'Last Author'), True),
        ('workflow_state', MSG(u'State'), True)]

    form.actions = [
        RemoveButton, RenameButton, CopyButton, CutButton, PasteButton,
        PublishButton, RetireButton]


    # Schema
    ids = multiple_choice_field(required=True)

    def ids__is_valid(self):
        return True


    # Keep the batch in the canonical URL
    canonical_query_parameters = (
        stl_view.canonical_query_parameters + ['batch_start'])


    def get_item_value(self, item, column):
        if column == 'checkbox':
            # checkbox
            parent = item.get_parent()
            if parent is None:
                return None
            if item.get_name() in parent.__fixed_handlers__:
                return None
            id = str(item.path)
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
        elif column == 'workflow_state':
            # The workflow state
            return item.get_workflow_preview()


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
        context = self.context
        ids = sorted(self.ids.value, reverse=True)
        for path in ids:
            child = context.get_resource(path)
            ac = child.access_control
            if ac.is_allowed_to_remove(user, child):
                # Remove resource
                try:
                    context.del_resource(path)
                except ConsistencyError:
                    referenced.append(path)
                    continue
                removed.append(path)
                # Clean cookie
                if path in paths:
                    context.del_cookie('ikaaro_cp')
                    paths = []
            else:
                not_removed.append(path)

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
        ac = resource.access_control
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
        ac = resource.access_control
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
        ac = resource.access_control
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
        from workflow import WorkflowAware

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
                    if issubclass(copy, WorkflowAware):
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
        ac = resource.access_control
        allowed = [ x for x in resources
                    if ac.is_allowed_to_trans(user, x, transition) ]
        if not allowed:
            context.message = messages.MSG_NONE_ALLOWED
            return

        # Publish
        for item in allowed:
            if item.get_workflow_state() == statename:
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



class Folder_Gallery_Content(stl_view):

    template = 'folder/gallery.xml'
    image_size = image_size_field(source='query', width=128, height=128)


    @thingy_property
    def rows(self):
        from workflow import WorkflowAware

        root_view = self.view.view
        image_size = self.image_size.encoded_value

        has_actions = bool(root_view.form.actions)

        rows = []
        for item in root_view.batch.items:
            is_folder = (item.class_id == 'folder')
            row = {
                'title': item.get_value('title'),
                'checkbox': has_actions,
                'is_folder': is_folder}

            # Checkbox
            if has_actions:
                id, checked = root_view.get_item_value(item, 'checkbox')
                row['id'] = id
                row['checked'] = checked
                if issubclass(item, WorkflowAware):
                    row['workflow_statename'] = item.get_workflow_state()
                else:
                    row['workflow_statename'] = None

            # XXX Already hard-coded in the catalog search
            value = root_view.get_item_value(item, 'name')
            if type(value) is tuple:
                value, href = value
                href = get_reference(href)
                if is_folder:
                    href = href.resolve_name(';gallery')
                href = href.replace(image_size=image_size)
                href = str(href)
            else:
                href = None
            row['name'] = value
            row['href'] = href
            rows.append(row)

        return rows


    @thingy_property
    def root(self):
        return self.resource.path == '/'


    @thingy_property
    def widths(self):
        # FIXME hardcoded
        sizes = ['640x480', '800x600', '1024x768', '1280x1024']
        return ", ".join(sizes)



class Folder_Gallery(Folder_Table):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Gallery')
    styles = ['/ui/gallery/style.css']
    scripts = ['/ui/gallery/javascript.js']

    template = make_stl_template("${search}${sort}${batch}${form}")

    context_menus = [ZoomMenu()]
    search = Folder_Search()
    search.base_query = OrQuery(PhraseQuery('is_image', True),
                                PhraseQuery('format', 'folder'))

    # Fields
    batch = Folder_Batch()
    batch.batch_size = batch.batch_size(value=0)

    # Form
    form = Folder_Table.form()
    form.content = Folder_Gallery_Content


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
    view_description = MSG(u"Show resources not linked from anywhere.")


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



class Folder_Thumbnail(view):

    access = True

    default_icon = 'gallery/folder.png'

    width = integer_field(source='query', value=48)
    height = integer_field(source='query', value=48)


    def get_mtime(self, resource):
        return resource.get_mtime()


    def http_get(self):
        default_icon = ui.get_template(self.default_icon)
        if PILImage is None:
            # Full size but better than nothing
            data = default_icon.to_str()
            format = 'png'
        else:
            width = self.width.value
            height = self.height.value
            data, format = default_icon.get_thumbnail(width, height)

        # XXX Cache nothing here
        # The image thumbnail was cached in the image handler
        # The folder thumbnail was cached in the folder handler
        # Accessible images depend on too many parameters
        context = self.context
        context.ok('image/%s' % format, data)



class GoToSpecificDocument(view):

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

