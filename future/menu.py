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

# Import from itools
from itools.datatypes import String, Enumerate, Unicode, Integer
from itools.xml import XMLParser
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.buttons import Button
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.forms import TextWidget, SelectWidget, ReadOnlyWidget
from ikaaro.forms import stl_namespaces
from ikaaro import messages
from ikaaro.registry import register_resource_class
from ikaaro.resource_views import Breadcrumb, DBResource_AddLink
from ikaaro.table import OrderedTableFile, OrderedTable
from ikaaro.table_views import OrderedTable_View



class PathWidget(TextWidget):

    template = TextWidget.template + list(XMLParser("""
        <input id="trigger_link" type="button" value="..."
               name="trigger_link"
               onclick="popup(';add_link?target_id=${name}&amp;mode=menu',
                              620, 300);"/>
        """, stl_namespaces))



class Target(Enumerate):

    options = [{'name': '_blank', 'value': MSG(u'New page')},
               {'name': '_top', 'value': MSG(u'Current page')}]



class MenuFile(OrderedTableFile):

    record_schema = {
        'title': Unicode,
        'path': String,
        'target': Target(mandatory=True, default='_top'),
        'child': String}



class ChildButton(Button):

    access = 'is_allowed_to_edit'
    name = 'add_child'
    title = MSG(u'Add Child')
    css = 'button_add'



class Menu_View(OrderedTable_View):

    schema = {
        'ids': Integer(multiple=True, mandatory=True),
    }

    table_actions = [ChildButton] + OrderedTable_View.table_actions


    def get_items(self, resource, context):
        items = resource.handler.get_records_in_order()
        return list(items)


    def get_table_columns(self, resource, context):
        columns = [
            ('checkbox', None),
            ('id', MSG(u'id'))]
        # From the schema
        for widget in self.get_widgets(resource, context):
            if widget.name == 'path':
                continue
            column = (widget.name, getattr(widget, 'title', widget.name))
            columns.append(column)

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'title':
            return item.title, item.path
        elif column == 'child':
            child = None
            parent = resource.parent
            if item.child and parent.has_resource(item.child):
                child = parent.get_resource(item.child)
                child = 'edit', resource.get_pathto(child)
            return child

        return OrderedTable_View.get_item_value(self, resource, context, item,
                                               column)


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.before_remove_record(id)
            resource.handler.del_record(id)

        context.message = MSG(u'Record deleted.')


    def action_order_up(self, resource, context, form):
        ids = form['ids']
        if not ids:
            context.message = MSG(u'Please select the objects to order up.')
            return

        resource.handler.order_up(ids)
        context.message = MSG(u'Objects ordered up.')


    def action_order_down(self, resource, context, form):
        ids = form['ids']
        if not ids:
            context.message = MSG(u'Please select the objects to order down.')
            return

        resource.handler.order_down(ids)
        context.message = MSG(u'Objects ordered down.')


    def action_order_top(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = MSG(u'Please select the objects to order on top.')
            context.message = message
            return

        resource.handler.order_top(ids)
        context.message = MSG(u'Objects ordered on top.')


    def action_order_bottom(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = MSG(u'Please select the objects to order on bottom.')
            context.message = message
            return

        resource.handler.order_bottom(ids)
        context.message = MSG(u'Objects ordered on bottom.')


    def action_add_child(self, resource, context, form):
        for parent_id in form['ids']:
            # generate the name of the new table
            parent_record = resource.handler.get_record(parent_id)
            # check if the child already exists
            child_path = parent_record.child
            if child_path and resource.parent.has_resource(child_path):
                continue

            parent = resource.parent
            names = parent.get_names()
            index = len(names) / 2
            base = 'menu_'
            name = '%s%03d' % (base, index)

            while name in names:
                index = index + 1
                name = '%s%03d' % (base, index)

            context.commit = True
            object = Menu.make_resource(Menu, resource.parent, name)

            # update the parent record
            resource.handler.update_record(parent_id,
                                           **{'child': name})

        context.message = messages.MSG_NEW_RESOURCE



class Menu_AddLink(DBResource_AddLink):

    access = 'is_allowed_to_edit'
    template = '/ui/future/menu_addlink.xml'

    def get_namespace(self, resource, context):
        namespace = DBResource_AddLink.get_namespace(self, resource, context)

        # For the breadcrumb
        if isinstance(resource, Menu):
            start = resource.parent.parent
        else:
            start = resource.parent

        # Construct namespace
        namespace['bc'] = Breadcrumb(filter_types=(File,), start=start,
                                     icon_size=48)
        namespace['target_id'] = context.get_form_value('target_id')

        return namespace



class Menu(OrderedTable):

    class_id = 'ikaaro-menu'
    class_title = MSG(u'iKaaro Menu')
    class_handler = MenuFile
    class_views = ['view', 'add_record']

    # Views
    view = Menu_View()
    add_link = Menu_AddLink()

    form = [TextWidget('title', title=MSG(u'Title')),
            PathWidget('path', title=MSG(u'Path')),
            SelectWidget('target', title=MSG(u'Target')),
            ReadOnlyWidget('child')]


    def before_remove_record(self, id):
        record = self.handler.get_record(id)
        child_path = record.child
        container = self.parent
        if child_path and container.has_resource(child_path):
            child = container.get_resource(child_path)
            for record_id in child.handler.get_record_ids():
                child.before_remove_record(record_id)
            container.del_resource(child_path)


    def get_menu_namespace_level(self, context, url, depth=2,
                                 use_first_child=False, flat=False):
        parent = self.parent
        site_root = context.site_root
        here, user = context.resource, context.user
        items = []
        tabs = {}
        for record in self.handler.get_records_in_order():
            get = record.get_value
            # Get the objects, check security
            path = get('path')
            # Subtabs
            subtabs = {}
            if path.startswith(('http://', 'https://')) or path.count(';'):
                # Special case for external link & method
                items.append({'id': 'menu_', # FIXME
                              'path': path,
                              'title': get('title'),
                              'description': None, # FIXME
                              'in_path': False,
                              'active': False,
                              'class': None,
                              'target': get('target')})
            else:
                resource = self.get_resource(path)
                name = resource.name

                ac = resource.get_access_control()
                if ac.is_allowed_to_view(user, resource) is False:
                    continue

                if depth > 1:
                    # Check the child
                    child_path = get('child')
                    if child_path and parent.has_resource(child_path):
                        # Sub level
                        child = parent.get_resource(child_path)
                        get_menu_ns_lvl = child.get_menu_namespace_level
                        subtabs = get_menu_ns_lvl(context, url, depth - 1,
                                                  use_first_child, flat)
                # Set active, in_path
                active, in_path = False, name in url
                if here.get_abspath() == resource.get_abspath():
                    active, in_path = True, False

                # Set css class to 'active', 'in_path' or None
                css = (active and 'in_path') or (in_path and 'in_path') or None

                items.append({'id': 'menu_%s' % name,
                              'path': context.get_link(resource),
                              'title': get('title'),
                              'description': None, # FIXME
                              'in_path': css == 'in_path' or active,
                              'active': active,
                              'class': css,
                              'target': get('target')})
            items[-1]['items'] = subtabs.get('items', [])
        tabs['items'] = items
        return tabs



class MenuFolder(Folder):

    class_id = 'menu-folder'
    class_title = MSG(u'iKaaro Menu')
    __fixed_handlers__ = Folder.__fixed_handlers__ + ['menu']
    # Your menu ressource (for overriding the record_schema and form)
    class_menu = Menu

    @staticmethod
    def _make_resource(cls, folder, name, **kw):
        Folder._make_resource(cls, folder, name, **kw)
        # Menu root
        cls_menu = cls.class_menu
        cls_menu._make_resource(cls_menu, folder, '%s/menu' % name,
                                title={'en': u"Menu", 'fr': u"Menu"})


    def get_document_types(self):
        return []


    def get_menu_namespace_level(self, context, url, depth=2,
                                 use_first_child=False, flat=False):
        menu_root = self.get_resource('menu')
        return menu_root.get_menu_namespace_level(context, url, depth,
                                                  use_first_child, flat)



def get_menu_namespace(context, depth=3, show_first_child=False, flat=True,
                       src=None):
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

    If "flat" is true (the default), the menu is also represented with a
    flattened structure:

    {'items': [...],
     'flat': {'lvl0': [item_dic01, ..., item_dic0N],
              'lvl1': [item_dic11, ..., item_dic1N],
              [...]
              'lvlN': [item_dicN1, ..., item_dicNN]}}

    "items" contains the first level. Each item_dic contains in turn an 'items'
    with its children.
    "class" is a CSS class decorating the item when active on within the
    current path.
    "id" is a CSS id to uniquely identify the item, based on the title.
    "target" is the anchor target (opening a new window or not).

    Activate "use_first_child" to automatically point to the first child of
    each item instead of the item itself.
    """

    request = context.request
    request_uri = str(request.request_uri)
    site_root = context.resource.get_site_root()
    method = context.view_name or context.resource.get_default_view_name()
    path = context.uri.path
    url = [seg.name for seg in path if seg.name]
    if method:
        url += [';%s' % method]

    # Get the menu
    tabs = {'items': []}
    if src is None:
        src = 'menu'
    if site_root.has_resource(src):
        menu = site_root.get_resource(src)
        tabs = menu.get_menu_namespace_level(context, url, depth,
                                             show_first_child)

    if flat:
        tabs['flat'] = {}
        items = tabs['flat']['lvl0'] = tabs.get('items', None)
        # initialize the levels
        for i in range(1, depth):
            tabs['flat']['lvl%s' % i] = None
        exist_items = True
        lvl = 1
        while (items is not None) and exist_items:
            exist_items = False
            for item in items:
                if item['class'] in ['active', 'in_path']:
                    if item['items']:
                        items = exist_items = item['items']
                        if items:
                            tabs['flat']['lvl%s' % lvl] = items
                            lvl += 1
                        break
                    else:
                        items = None
                        break
    return tabs

#
# Register
#
register_resource_class(Menu)
register_resource_class(MenuFolder)
