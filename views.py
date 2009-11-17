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

# Import from itools
from itools.core import freeze, thingy_property, thingy_lazy_property
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import get_reference
from itools.web import BaseView, STLView, STLForm
from itools.web import boolean_field, choice_field, hidden_field, integer_field
from itools.web import text_field
from itools.xml import XMLParser

# Import from ikaaro
from globals import ui
from utils import CMSTemplate


"""This module contains some generic views used by different resources.
"""


class CompositeView(STLView):

    template = '/ui/generic/cascade.xml'
    subviews = []


    def get_query_schema(self):
        schema = {}
        for view in self.subviews:
            view_schema = view.get_query_schema()
            for key in view_schema:
                if key in schema:
                    msg = 'query schema key "%s" defined twice'
                    raise ValueError, msg % key
                schema[key] = view_schema[key]
        return schema


    def get_namespace(self, resource, context):
        views = [ view.GET(resource, context) for view in self.subviews ]
        return {'views': views}



class CompositeForm(CompositeView, STLForm):
    """This view renders the sub-views defined by the class variable
    'subviews' one after the other.
    """

    def get_schema(self, resource, context):
        # Check for specific schema
        action = self.action_name
        for view in self.subviews:
            method = getattr(view, action, None)
            if method is None:
                continue
            schema = getattr(view, '%s_schema' % action, None)
            if schema is not None:
                return schema
            return view.get_schema(resource, context)
        return {}


    def get_action_method(self, resource, context):
        for view in self.subviews:
            method = getattr(view, self.action_name, None)
            if method is not None:
                return method
        return None



class MessageView(BaseView):

    def render(self):
        message = self.message
        message = message.gettext()
        message = message.encode('utf-8')
        return XMLParser(message)



class IconsView(STLView):
    """This view draws a menu where each menu item is made up of a big
    icon (48x48 pixels), a title and a description.
    """

    template = 'generic/icons_view.xml'

    # Namespace
    batch = None
    items = freeze([])



###########################################################################
# Menu
###########################################################################
class ContextMenu(CMSTemplate):

    template = 'generic/menu.xml'

    def get_items(self):
        """The input (options) is a tree:

          [{'href': ...,
            'class': ...,
            'src': ...,
            'title': ...,
            'items': [....]}
           ...
           ]
        """
        raise NotImplementedError


    @thingy_lazy_property
    def content_language(self):
        return self.resource.get_content_language()


    def items(self):
        items = self.get_items()
        # Defaults
        for item in items:
            for name in ['class', 'src', 'items']:
                item.setdefault(name, None)

        return items



###########################################################################
# Search, batch, table
###########################################################################

class Container_Search(STLView):

    template = 'generic/search.xml'
    term = text_field(source='query')

    @thingy_lazy_property
    def items(self):
        raise NotImplementedError


    @thingy_lazy_property
    def total(self):
        return len(self.items)



class Container_Sort(STLView):

    template = 'generic/sort.xml'

    sort_by = choice_field(source='query')
    reverse = boolean_field(source='query')



class Container_Batch(STLView):

    template = 'generic/batch.xml'

    # FIXME Use plural forms
    msg1 = MSG(u"There is 1 item.")
    msg2 = MSG(u"There are {n} items.")

    # Fields
    batch_start = integer_field(source='query', value=0)
    batch_size = integer_field(source='query', value=20)


    @thingy_lazy_property
    def start(self):
        return self.batch_start.value + 1


    @thingy_property
    def total(self):
        return self.view.search.total


    @thingy_lazy_property
    def size(self):
        # If batch_size == 0 => All
        size = self.batch_size.value
        return self.total if size == 0 else size


    @thingy_lazy_property
    def end(self):
        start = self.batch_start.value
        return min(start + self.size, self.total)


    def msg(self):
        total = self.total
        if total == 1:
            return self.msg1.gettext()
        return self.msg2.gettext(n=total)


    def control(self):
        start = self.batch_start.value
        return (start > 0) or (self.end < self.total)


    @thingy_lazy_property
    def batch_previous(self):
        start = self.batch_start.value
        if start > 0:
            uri = get_reference(self.context.uri)
            previous = max(start - self.size, 0)
            previous = str(previous)
            return uri.replace(batch_start=previous)

        return None


    @thingy_lazy_property
    def batch_next(self):
        end = self.end
        if end < self.total:
            uri = get_reference(self.context.uri)
            next = str(end)
            return uri.replace(batch_start=next)

        return None


    @thingy_lazy_property
    def items(self):
        raise NotImplementedError



class Container_Form(STLForm):

    template = 'generic/form.xml'

    subviews = ['content']

    @thingy_lazy_property
    def actions_ns(self):
        items = self.view.batch.items

        actions = []
        for button in self.actions:
            if button.show(self.resource, self.context, items) is False:
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
        return actions




class Container_Table(STLForm):

    template = 'generic/table.xml'
    css = None
    header = []
    actions = []

    # Actions are external to current form
    external_form = False

    def get_table_columns(self):
        return self.header


    def columns(self):
        # Get from the query
        sort_by = self.root_view.sort.sort_by.value
        reverse = self.root_view.sort.reverse.value

        columns = self.get_table_columns()
        columns_ns = []
        uri = get_reference(self.context.uri)
        for name, title, sortable in columns:
            if name == 'checkbox':
                # Type: checkbox
                if self.external_form or self.actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None or not sortable:
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
        columns = self.get_table_columns()
        rows = []
        for item in self.root_view.batch.items:
            row_columns = []
            for column in columns:
                column = column[0]
                # Skip the checkbox column if there are not any actions
                if column == 'checkbox':
                    if not self.external_form and not self.actions:
                        continue

                value = self.root_view.get_item_value(item, column)
                column_ns = {
                    'is_checkbox': False,
                    'is_icon': False,
                    'is_link': False}
                # Type: empty
                if value is None:
                    pass
                # Type: checkbox
                elif column == 'checkbox':
                    value, checked = value
                    column_ns['is_checkbox'] = True
                    column_ns['value'] = value
                    column_ns['checked'] = checked
                # Type: icon
                elif column == 'icon':
                    column_ns['is_icon'] = True
                    column_ns['src'] = value
                # Type: normal
                else:
                    column_ns['is_link'] = True
                    if type(value) is tuple:
                        value, href = value
                    else:
                        href = None
                    column_ns['value'] = value
                    column_ns['href'] = href
                row_columns.append(column_ns)

            # Append
            rows.append({'columns': row_columns})

        # Ok
        return rows


    def get_item_value(self, item, column):
        name = 'get_item_value'
        raise NotImplementedError, "the '%s' method is not defined" % name

