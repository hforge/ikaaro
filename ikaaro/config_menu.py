# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Henry Obein <henry@itaapy.com>
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from copy import deepcopy

# Import from itools
from itools.gettext import MSG
from itools.handlers import checkid
from itools.uri import Path

# Import from ikaaro
from autoadd import AutoAdd
from autoedit import AutoEdit
from autoform import PathSelectorWidget
from config import Configuration
from config_common import NewResource_Local
from buttons import Remove_BrowseButton
from fields import Select_Field, URI_Field
from order import OrderedFolder, OrderedFolder_BrowseContent
from utils import split_reference



class Target_Field(Select_Field):

    default = '_top'
    options = [{'name': '_top', 'value': MSG(u'Current page')},
               {'name': '_blank', 'value': MSG(u'New page')}]

    required = True
    title = MSG(u'Target')
    has_empty_option = False



class MenuItem_Browse(OrderedFolder_BrowseContent):

    search_widgets = None
    table_columns = [
        ('checkbox', None),
        ('abspath', MSG(u'Path')),
        ('title', MSG(u'Title')),
        ('target', MSG(u'Target')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author')),
        ('order', MSG(u'Order'))]
    table_actions = [Remove_BrowseButton]

    def get_item_value(self, resource, context, item, column):
        if column == 'title':
            return item.get_title(), item.get_value('path')

        proxy = super(MenuItem_Browse, self)
        return proxy.get_item_value(resource, context, item, column)


class AddMenu(NewResource_Local):

    title = MSG(u'Add item')

    def get_items(self, resource, context):
        return tuple(resource.get_document_types())



class MenuItem(OrderedFolder):

    class_id = 'config-menu-item'
    class_title = MSG(u'Menu')

    # Fields
    path = URI_Field(required=True, title=MSG(u'Path'),
                     widget=PathSelectorWidget)
    target = Target_Field

    def get_document_types(self):
        return [MenuItem]

    # Views
    class_views = ['edit', 'browse_content', 'add_menu', 'commit_log']
    _fields = ['title', 'path', 'target']
    new_instance = AutoAdd(fields=_fields)
    edit = AutoEdit(fields=_fields)
    browse_content = MenuItem_Browse
    add_menu = AddMenu


    # API
    def _is_allowed_to_access(self, context, uri):
        # Get the reference and path
        ref, path, view = split_reference(uri)

        # Broken entry
        if ref is None or path == '':
            return False

        # External link
        if ref.scheme:
            return True

        # Broken link
        resource = self.get_resource(path, soft=True)
        if resource is None:
            return False

        if view:
            # Remove the first '/;' of the view
            view = resource.get_view(view[2:], ref.query)
            if not view:
                return False
            # Check ACL
            return context.is_access_allowed(resource, view)

        # Check if the user can access to resource views
        # get_views checks ACLs with by calling is_access_allowed
        resource_views = list(resource.get_views())
        return len(resource_views) > 0


    def get_menu_namespace_level(self, context, url, use_first_child=False):
        menu_abspath = self.abspath
        here = context.resource
        here_abspath = here.abspath
        here_view_name = url[-1]
        here_abspath_and_view = '%s/%s' % (here_abspath, here_view_name)
        items = []

        for resource in self.get_resources_in_order():
            uri = resource.get_value('path')
            if not self._is_allowed_to_access(context, uri):
                continue
            ref, path, view = split_reference(uri)
            title = resource.get_value('title')
            target = resource.get_value('target')

            # Case 1: External link
            if ref.scheme:
                items.append({
                    'id': 'menu_%s' % resource.name,
                    'path': str(ref),
                    'real_path': None,
                    'title': title,
                    'description': None,
                    'in_path': False,
                    'active': False,
                    'class': None,
                    'target': target,
                    'items': []})
                continue

            # Case 2: Internal link
            # Sub level
            subtabs = resource.get_menu_namespace_level(context, url,
                                                        use_first_child)
            resource = self.get_resource(path, soft=True)
            item_id = 'menu_%s' % resource.name

            # Use first child by default we use the resource itself
            resource_path = path
            # Keep the real path to avoid highlight problems
            resource_original_path = path
            # use first child
            if use_first_child and subtabs:
                sub_path = subtabs[0]['real_path']
                # if the first child is an external link => skip it
                if sub_path is not None:
                    resource_path = sub_path

            # Set active, in_path
            active = in_path = False
            # add default view
            if view:
                resource_method = view[2:]
                item_id += '_%s' % resource_method
            else:
                resource_method = resource.get_default_view_name()
            resource_abspath_and_view = '%s/;%s' % (resource.abspath,
                                                    resource_method)
            if here_abspath_and_view == resource_abspath_and_view:
                active = True
            else:
                # Use the original path for the highlight
                res_abspath = menu_abspath.resolve2(resource_original_path)
                common_prefix = here_abspath.get_prefix(res_abspath)
                # Avoid to always set the root entree 'in_path'
                # If common prefix equals root abspath set in_path to False
                # otherwise compare common_prefix and res_abspath
                if common_prefix != Path('/'):
                    in_path = (common_prefix == res_abspath)

            # Build the new reference with the right path
            ref2 = deepcopy(ref)
            resource = self.get_resource(resource_path)
            ref2.path = context.get_link(resource)
            if view:
                ref2.path += view

            items.append({
                'id': item_id,
                'path': str(ref2),
                'real_path': resource.abspath,
                'title': title,
                'description': None, # FIXME
                'in_path': active or in_path,
                'active': active,
                'class': None,
                'target': target,
                'items': subtabs})

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

        if len(items) > 0:
            # Add class "first" to the first item
            css = items[0]['class'] or ''
            items[0]['class'] = css + ' first'
            # Add class "last" to the last item
            css = items[-1]['class'] or ''
            items[-1]['class'] = css + ' last'

        return items



###########################################################################
# Configuration
###########################################################################
class ConfigMenu(MenuItem):

    class_id = 'config-menu'
    class_title = MSG(u'Configuration Menu')
    class_description = MSG(u'Edit the global menu.')
    class_icon48 = 'icons/48x48/menu.png'

    def init_resource(self, **kw):
        super(ConfigMenu, self).init_resource(**kw)
        # Menu
        order = []
        menus = [('/', u'Home'), ('/;contact', u'Contact')]
        for path, title in menus:
            name = checkid(title)
            order.append(name)
            self.make_resource(name, MenuItem, path=path,
                               title={'en': title})
        self.set_property('order', order)

    # Configuration
    config_name = 'menu'
    config_group = 'webmaster'

    # Views
    class_views = ['browse_content', 'add_menu', 'edit', 'commit_log']


    def get_menu_namespace(self, context, show_first_child=False, src=None):
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

        "items" contains the first level. Each item_dic contains in turn an
        'items' with its children.
        "class" is a CSS class decorating the item when active on within the
        current path.
        "id" is a CSS id to uniquely identify the item, based on the title.
        "target" is the anchor target (opening a new window or not).

        Activate "use_first_child" to automatically point to the first child
        of each item instead of the item itself.
        """
        resource = context.resource
        url = list(context.uri.path)
        if not url or url[-1][0] != ';':
            method = resource.get_default_view_name()
            url.append(';%s' % method)

        # Get the menu
        menu = self
        if src:
            menu = self.get_resource(src, soft=True)
            if menu is None:
                return []

        return menu.get_menu_namespace_level(context, url, show_first_child)



# Register
Configuration.register_module(ConfigMenu)
