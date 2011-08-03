# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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

# Import from standard Library
from copy import deepcopy

# Import from itools
from itools.datatypes import String, Enumerate, Integer, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.uri import Path
from itools.web import get_context
from itools.xml import XMLParser

# Import from ikaaro
from autoform import PathSelectorWidget, ReadOnlyWidget, SelectWidget
from buttons import BrowseButton, Button
from exceptions import ConsistencyError
from folder import Folder
from folder_views import Folder_BrowseContent, Folder_PreviewContent
from folder_views import Folder_NewResource
from folder_views import Folder_Rename, GoToSpecificDocument
from folder_views import Folder_Thumbnail
from popup import DBResource_AddLink
from revisions_views import DBResource_CommitLog
from table import OrderedTableFile, OrderedTable
from table_views import OrderedTable_View
from table_views import Table_AddRecord, Table_EditRecord
from utils import split_reference
from workflow import get_workflow_preview
import messages



class NotAllowedError(Exception):
    pass



class Target(Enumerate):

    options = [{'name': '_top', 'value': MSG(u'Current page')},
               {'name': '_blank', 'value': MSG(u'New page')}]


class TargetWidget(SelectWidget):
    has_empty_option = False



class MenuFile(OrderedTableFile):

    record_properties = {
        'title': Unicode(mandatory=True, multilingual=True,
                         title=MSG(u'Title')),
        'path': String(mandatory=True, title=MSG(u'Path'),
                       widget=PathSelectorWidget),
        'target': Target(mandatory=True, default='_top', title=MSG(u'Target'),
                         widget=TargetWidget),
        'child': String(title=None, widget=ReadOnlyWidget)}



class ChildButton(BrowseButton):

    access = 'is_allowed_to_edit'
    name = 'add_child'
    title = MSG(u'Add Child')
    css = 'button-add'



class Menu_View(OrderedTable_View):

    access = 'is_allowed_to_edit'
    schema = {
        'ids': Integer(multiple=True, mandatory=True)}

    def get_table_actions(self, resource, context):
        table_actions = OrderedTable_View.get_table_actions(self, resource,
                                                            context)
        # Add submenu column if needed
        if resource.parent.allow_submenu:
            return [ChildButton] + table_actions
        return table_actions


    def get_table_columns(self, resource, context):
        proxy = super(Menu_View, self)
        base_columns = proxy.get_table_columns(resource, context)

        columns_to_skip = ['path']
        if not resource.parent.allow_submenu:
            columns_to_skip.append('child')

        columns = [ c for c in base_columns
                    if c[0] not in columns_to_skip ]

        return columns


    def get_item_value(self, resource, context, item, column):
        get_value = resource.handler.get_record_value
        value = get_value(item, column)
        if column == 'title':
            path = get_value(item, 'path')
            # Get the reference and path
            ref, path, view = split_reference(path)
            if ref.scheme:
                # External link
                return value, path
            if path.is_absolute():
                path = context.root.abspath.resolve2('.%s' % path)
            resource_item = resource.get_resource(path, soft=True)
            # Broken link
            if resource_item is None:
                return value
            # Build the new reference with the right path
            ref2 = deepcopy(ref)
            ref2.path = context.get_link(resource_item)
            return value, str(ref2)
        elif column == 'child':
            if not value:
                return None
            child = resource.parent.get_resource(value, soft=True)
            if child is None:
                return None
            return 'edit', context.get_link(child)
        elif column == 'state':
            path = get_value(item, 'path')
            if not path:
                # Do not display a workflow state if there is no path defined.
                return
            # Get the reference and path
            ref, path, view = split_reference(path)
            if ref.scheme:
                # External link
                return None
            if path.is_absolute():
                path = context.root.abspath.resolve2('.%s' % path)
            item_resource = resource.get_resource(path, soft=True)
            # Broken link
            if item_resource is None:
                title = MSG(u'The resource does not exist anymore.')
                title = title.gettext().encode('utf-8')
                label = MSG(u'Broken').gettext().encode('utf-8')
                link = context.get_link(resource)
                state = ('<a href="%s/;edit_record?id=%s" class="workflow"'
                         'title="%s"><strong class="broken">%s</strong>'
                         '</a>') % (link, item.id, title, label)
                return XMLParser(state)
            # The workflow state
            return get_workflow_preview(item_resource, context)

        return OrderedTable_View.get_item_value(self, resource, context, item,
                                                column)


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        removed = []
        not_removed = []
        referenced = []
        for id in ids:
            try:
                resource.del_record(id)
            except ConsistencyError:
                referenced.append(str(id))
            except NotAllowedError:
                not_removed.append(str(id))
            else:
                removed.append(str(id))

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

        # Reindex the resource
        context.database.change_resource(resource)


    def action_add_child(self, resource, context, form):
        handler = resource.handler
        parent = resource.parent
        menu_cls = parent.class_menu

        for parent_id in form['ids']:
            # generate the name of the new table
            parent_record = handler.get_record(parent_id)
            # check if the child already exists
            child_path = handler.get_record_value(parent_record, 'child')
            if child_path and parent.get_resource(child_path, soft=True):
                continue

            names = parent.get_names()
            index = len(names) / 2
            base = 'menu '
            name = checkid('%s%03d' % (base, index))

            while name in names:
                index = index + 1
                name = checkid('%s%03d' % (base, index))

            parent.make_resource(name, menu_cls)

            # update the parent record
            resource.update_record(parent_id, **{'child': name})

        context.message = messages.MSG_NEW_RESOURCE



class Menu_AddLink(DBResource_AddLink):

    def get_start(self, resource):
        return resource.get_root()



class Menu_AddRecord(Table_AddRecord):

    fields = ['title', 'path', 'target', 'child']

    actions = (Table_AddRecord.actions
               + [Button(access=True, name='add_and_return', css='button-ok',
                         title=MSG(u'Add and return'))])


    def action_add_and_return(self, resource, context, record):
        proxy = super(Menu_AddRecord, self)
        return proxy.action(resource, context, record)


    def action_on_success(self, resource, context):
        if context.form_action == 'action_add_and_return':
            goto = context.get_link(resource)
        else:
            n = len(resource.handler.records) - 1
            goto = ';edit_record?id=%s' % n
        return context.come_back(MSG(u'New record added.'), goto=goto)



class Menu_EditRecord(Table_EditRecord):

    fields = ['title', 'path', 'target', 'child']

    actions = (Table_EditRecord.actions
               + [Button(access=True, name='edit_and_return',
                         css='button-ok', title=MSG(u'Edit and return'))])

    def action_edit_and_return(self, resource, context, record):
        proxy = super(Menu_EditRecord, self)
        return proxy.action(resource, context, record)


    def action_on_success(self, resource, context):
        proxy = super(Menu_EditRecord, self)
        proxy.action_on_success(resource, context)

        if context.form_action == 'action_edit_and_return':
            goto = context.get_link(resource)
            return context.come_back(context.message, goto=goto)



class Menu(OrderedTable):

    class_id = 'ikaaro-menu'
    class_title = MSG(u'Menu item')

    table = OrderedTable.table(class_handler=MenuFile)

    # Views
    class_views = ['view', 'add_record']
    add_link = Menu_AddLink()
    add_record = Menu_AddRecord()
    edit_record = Menu_EditRecord()
    view = Menu_View()


    def del_record(self, id):
        handler = self.handler
        record = handler.get_record(id)
        schema = self.get_schema()

        # Delete submenu
        if 'child' in schema:
            child_path = handler.get_record_value(record, 'child')
            if child_path:
                container = self.parent
                child = container.get_resource(child_path, soft=True)
                if child is not None:
                    ac = child.get_access_control()
                    user = get_context().user
                    if ac.is_allowed_to_remove(user, child):
                        if child.handler.get_n_records():
                            raise NotAllowedError
                        # Remove the child table
                        # May raise a ConsistencyError
                        container.del_resource(child_path)
                    else:
                        raise NotAllowedError

        # Delete the record
        handler.del_record(id)
        get_context().database.change_resource(self)


    def _is_allowed_to_access(self, context, uri):
        # Get the reference and path
        ref, path, view = split_reference(uri)
        if ref.scheme:
            # External link
            return True

        user = context.user
        if ref is None or path == '':
            # Skip broken entry
            return False

        # Internal link
        resource = self.get_resource(path, soft=True)
        # Broken link
        if resource is None:
            return False

        if view:
            # remove the first '/;' of the view
            view = resource.get_view(view[2:], ref.query)
            if view:
                # Check ACL
                ac = resource.get_access_control()
                return ac.is_access_allowed(user, resource, view)
            # Broken view
            return False
        else:
            # Check if the user can access to resource views
            # get_views checks ACLs with by calling is_access_allowed
            resource_views = list(resource.get_views())
            return len(resource_views) > 0


    def get_menu_namespace_level(self, context, url, depth=2,
                                 use_first_child=False):
        parent = self.parent
        handler = self.handler
        menu_abspath = self.get_abspath()
        here = context.resource
        here_abspath = here.get_abspath()
        here_view_name = url[-1]
        here_abspath_and_view = '%s/%s' % (here_abspath, here_view_name)
        items = []
        tabs = {}
        get_value = handler.get_record_value
        for record in self.get_records_in_order():
            # Get the objects, check security
            uri = get_value(record, 'path')
            if self._is_allowed_to_access(context, uri) is False:
                continue
            title = get_value(record, 'title')
            target = get_value(record, 'target')
            # Subtabs
            subtabs = {}
            # Get the reference and path
            ref, path, view = split_reference(uri)
            if ref.scheme:
                # Special case for external link
                items.append({'id': 'menu_%s' % record.id,
                              'path': str(ref),
                              'real_path': None,
                              'title': title,
                              'description': None,
                              'in_path': False,
                              'active': False,
                              'class': None,
                              'target': target})
            else:
                # Internal link
                resource = self.get_resource(path, soft=True)
                # Broken link
                if resource is None:
                    continue
                name = resource.name
                item_id = 'menu_%s' % name

                # Use first child by default we use the resource itself
                resource_path = path
                # Keep the real path to avoid highlight problems
                resource_original_path = path
                if depth > 1:
                    # Check the child
                    child_path = get_value(record, 'child')
                    if child_path:
                        child = parent.get_resource(child_path, soft=True)
                        if child is not None:
                            # Sub level
                            get_menu_ns_lvl = child.get_menu_namespace_level
                            subtabs = get_menu_ns_lvl(context, url, depth - 1,
                                                      use_first_child)
                            # use first child
                            if use_first_child and subtabs['items']:
                                sub_path = subtabs['items'][0]['real_path']
                                # if the first child is an external link =>
                                # skip it
                                if sub_path is not None:
                                    resource_path = sub_path

                # Set active, in_path
                active = in_path = False
                resource_abspath = resource.get_abspath()
                # add default view
                if view:
                    resource_method = view[2:]
                    item_id += '_%s' % resource_method
                else:
                    resource_method = resource.get_default_view_name()
                resource_abspath_and_view = '%s/;%s' % (resource_abspath,
                                                        resource_method)
                if here_abspath_and_view == resource_abspath_and_view:
                    active = True
                else:
                    # Use the original path for the highlight
                    res_abspath = menu_abspath.resolve2(resource_original_path)
                    common_prefix = here_abspath.get_prefix(res_abspath)
                    # Avoid to always set the root entree 'in_path'
                    # If common prefix equals root abspath set in_path to
                    # False otherwise compare common_prefix and res_abspath
                    if common_prefix != Path('/'):
                        in_path = (common_prefix == res_abspath)

                # Build the new reference with the right path
                ref2 = deepcopy(ref)
                resource = self.get_resource(resource_path)
                ref2.path = context.get_link(resource)
                if view:
                    ref2.path += view

                items.append({'id': item_id,
                              'path': str(ref2),
                              'real_path': resource.get_abspath(),
                              'title': title,
                              'description': None, # FIXME
                              'in_path': active or in_path,
                              'active': active,
                              'class': None,
                              'target': target})
            items[-1]['items'] = subtabs.get('items', [])

        # Set class
        x = None
        for i, item in enumerate(items):
            if item['active']:
                x = i
                break
            if item['in_path'] and x is None:
                x = i
                break
        if x is not None:
            items[x]['class'] = 'in-path'

        tabs['items'] = items
        return tabs


    def get_first_level_uris(self, context):
        """Return a list of the URI of all entries in the first level
        """
        get_value = self.handler.get_record_value
        uris = []
        for record in self.get_records_in_order():
            # Get the objects, check security
            uri = get_value(record, 'path')
            # Get the reference and path
            ref, path, view = split_reference(uri)
            if ref.scheme:
                # External link
                uris.append(ref)
                continue
            if self._is_allowed_to_access(context, uri) is False:
                continue
            resource = self.get_resource(path)
            # Build the new reference with the right path
            ref2 = deepcopy(ref)
            ref2.path = context.get_link(resource)
            uris.append(ref2)

        return uris


    def get_links(self):
        links = super(Menu, self).get_links()
        base = self.get_abspath()
        root_abspath = Path('/')
        schema = self.get_schema()
        handler = self.get_table()

        for record in self.get_records_in_order():
            # Target resources
            path = handler.get_record_value(record, 'path')
            ref, path, view = split_reference(path)
            if ref.scheme:
                continue
            if path.is_absolute():
                uri = path
            else:
                uri = base.resolve2(path)
            resource = self.get_resource(uri, soft=True)
            if resource:
                # Use the canonical path instead of the uri stocked
                link = str(resource.get_abspath())
            else:
                # If the resource does not exist, simply use the uri
                link = str(uri)
            links.add(link)

            # Submenu resources
            if not 'child' in schema:
                continue
            path = handler.get_record_value(record, 'child')
            if path:
                container = self.parent
                child = container.get_resource(path, soft=True)
                if child is not None:
                    uri = root_abspath.resolve(path)
                    links.add(str(uri))

        return links


    def update_links(self, source, target):
        super(Menu, self).update_links(source, target)
        base = self.get_abspath()
        resources_new2old = get_context().database.resources_new2old
        base = str(base)
        old_base = resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)
        handler = self.handler

        for record in self.get_records_in_order():
            path = handler.get_record_value(record, 'path')
            ref, path, view = split_reference(path)
            if ref.scheme:
                continue
            if path.is_absolute():
                uri = path
            else:
                uri = old_base.resolve2(path)
            if str(uri) == source:
                # Hit the old name
                # Build the new reference with the right path
                new_ref = deepcopy(ref)
                new_ref.path = str(new_base.get_pathto(target)) + view
                handler.update_record(record.id, **{'path': str(new_ref)})

        get_context().database.change_resource(self)


    def update_relative_links(self, source):
        super(Menu, self).update_relative_links(source)
        target = self.get_abspath()
        resources_old2new = get_context().database.resources_old2new
        handler = self.handler

        for record in self.get_records_in_order():
            path = handler.get_record_value(record, 'path')
            ref, path, view = split_reference(path)
            if ref.scheme:
                continue
            # Calcul the old absolute path
            if ref.path.is_absolute():
                old_abs_path = path
            else:
                old_abs_path = source.resolve2(path)
            # Check if the target path has not been moved
            new_abs_path = resources_old2new.get(old_abs_path, old_abs_path)
            # Build the new reference with the right path
            # Absolute path allow to call get_pathto with the target
            new_ref = deepcopy(ref)
            new_ref.path = str(target.get_pathto(new_abs_path)) + view
            handler.update_record(record.id, **{'path': str(new_ref)})



class MenuFolder(Folder):

    class_id = 'menu-folder'
    class_title = MSG(u'Menu')
    class_views = ['view']
    __fixed_handlers__ = Folder.__fixed_handlers__ + ['menu']
    # Your menu ressource (for overriding the record_properties and form)
    class_menu = Menu
    allow_submenu = False

    # Hide in browse_content
    is_content = False

    # Views
    view = GoToSpecificDocument(specific_document='menu',
                                title=MSG(u'View'),
                                access='is_allowed_to_edit')
    # Disable all default views
    new_resource = Folder_NewResource(access='is_admin')
    browse_content = Folder_BrowseContent(access='is_admin')
    rename = Folder_Rename(access='is_admin')
    preview_content = Folder_PreviewContent(access='is_admin')
    commit_log = DBResource_CommitLog(access='is_admin')
    thumb = Folder_Thumbnail(access='is_admin')


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # Menu root
        self.make_resource('menu', self.class_menu)


    def get_document_types(self):
        return []


    def get_menu_namespace_level(self, context, url, depth=2,
                                 use_first_child=False):
        menu_root = self.get_resource('menu')
        return menu_root.get_menu_namespace_level(context, url, depth,
                                                  use_first_child)


    def get_first_level_uris(self, context):
        menu_root = self.get_resource('menu')
        return menu_root.get_first_level_uris(context)



def get_menu_namespace(context, depth=3, show_first_child=False, src=None,
                       menu=None):
    """Return dict with the following structure:

    {'items': [item_dic01, ..., item_dic0N]}

    Where the list of items is the first level
    and item_dic = {'active': True or False,
                    'class': 'active' or 'in_path' or None,
                    'description': MSG(u'About Python'),
                    'id': 'tab_python',
                    'in_path': True or False,
                    'items': [item_dic11, ..., item_dic1N] or None,
                    'name': 'python',
                    'path': '../python',
                    'target': '_top' or '_blank' or None,
                    'title': MSG(u'Python')}

    "items" contains the first level. Each item_dic contains in turn an 'items'
    with its children.
    "class" is a CSS class decorating the item when active on within the
    current path.
    "id" is a CSS id to uniquely identify the item, based on the title.
    "target" is the anchor target (opening a new window or not).

    Activate "use_first_child" to automatically point to the first child of
    each item instead of the item itself.
    """
    resource = context.resource
    url = list(context.uri.path)
    if not url or url[-1][0] != ';':
        method = resource.get_default_view_name()
        url.append(';%s' % method)

    # Get the menu
    if src:
        menu = context.root.get_resource(src, soft=True)

    if menu is None:
        return {'items': []}

    return menu.get_menu_namespace_level(context, url, depth,
                                         show_first_child)
