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
from itools.core import merge_dicts
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import get_reference
from itools.web import STLView, STLForm
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
        action = context.form_action
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
            method = getattr(view, context.form_action, None)
            if method is not None:
                return method
        return None



class MessageView(STLView):

    template = 'generic/message_view.xml'

    def get_namespace(self, resource, context):
        message = self.message
        message = message.gettext()
        message = message.encode('utf-8')
        message = XMLParser(message)
        return {'message': message}




class IconsView(STLView):
    """This view draws a menu where each menu item is made up of a big
    icon (48x48 pixels), a title and a description.
    """

    template = 'generic/icons_view.xml'

    def get_namespace(self, resource, context):
        """TODO Write a docstring explaining the expected namespace.
        """
        raise NotImplementedError



###########################################################################
# Browse View (batch + table)
###########################################################################
class BrowseForm(STLForm):

    template = 'generic/browse.xml'

    query_schema = {
        'batch_start': Integer(default=0),
        'batch_size': Integer(default=20),
        'sort_by': String,
        'reverse': Boolean(default=False)}

    # Batch
    batch_template = 'generic/browse_batch.xml'
    batch_msg1 = MSG(u"There is 1 item.") # FIXME Use plural forms
    batch_msg2 = MSG(u"There are {n} items.")

    # Content
    table_template = 'generic/browse_table.xml'
    table_css = None
    table_columns = []
    table_actions = []
    # Actions are external to current form
    external_form = False

    # Keep the batch in the canonical URL
    canonical_query_parameters = (STLForm.canonical_query_parameters
                                  + ['batch_start'])


    def get_namespace(self, resource, context):
        batch = None
        table = None
        # Batch
        items = self.get_items(resource, context)
        if self.batch_template is not None:
            template = ui.get_template(self.batch_template)
            namespace = self.get_batch_namespace(resource, context, items)
            batch = stl(template, namespace)

        # Content
        items = self.sort_and_batch(resource, context, items)
        if self.table_template is not None:
            template = ui.get_template(self.table_template)
            namespace = self.get_table_namespace(resource, context, items)
            table = stl(template, namespace)

        return {'batch': batch, 'table': table}


    #######################################################################
    # Private API (to override)
    def get_table_columns(self, resource, context):
        return self.table_columns


    def _get_table_columns(self, resource, context):
        """ Always return a tuple of 3 elements. """
        table_columns = []
        for column in self.get_table_columns(resource, context):
            if len(column) == 2:
                name, title = column
                column = (name, title, True)
            table_columns.append(column)
        return table_columns


    def get_items(self, resource, context):
        name = 'get_items'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def sort_and_batch(self, resource, context, items):
        name = 'sort_and_batch'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def get_item_value(self, resource, context, item, column):
        name = 'get_item_value'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def get_table_actions(self, resource, context):
        return self.table_actions


    #######################################################################
    # Batch
    def get_batch_namespace(self, resource, context, items):
        namespace = {}
        namespace['control'] = False

        # Message (singular or plural)
        total = len(items)
        if total == 1:
            namespace['msg'] = self.batch_msg1.gettext()
        else:
            namespace['msg'] = self.batch_msg2.gettext(n=total)

        # Start & End
        start = context.get_query_value('batch_start')
        size = context.get_query_value('batch_size')
        # If batch_size == 0 => All
        if size == 0:
            size = total
        end = min(start + size, total)
        namespace['start'] = start + 1
        namespace['end'] = end

        # Previous
        uri = get_reference(context.uri)
        if start > 0:
            previous = max(start - size, 0)
            previous = str(previous)
            namespace['previous'] = uri.replace(batch_start=previous)
            namespace['control'] = True
        else:
            namespace['previous'] = None

        # Next
        if end < total:
            next = str(end)
            namespace['next'] = uri.replace(batch_start=next)
            namespace['control'] = True
        else:
            namespace['next'] = None

        # Ok
        return namespace


    #######################################################################
    # Table
    def get_table_head(self, resource, context, items, actions=None):
        # Get from the query
        sort_by = context.get_query_value('sort_by')
        reverse = context.get_query_value('reverse')

        columns = self._get_table_columns(resource, context)
        columns_ns = []
        for name, title, sortable in columns:
            if name == 'checkbox':
                # Type: checkbox
                if self.external_form or actions:
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
                uri = get_reference(context.uri)
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
                    'sort_down_active': sort_down_active
                    })
        return columns_ns


    def get_table_namespace(self, resource, context, items):
        ac = resource.get_access_control()

        # (1) Actions (submit buttons)
        actions = []
        for button in self.get_table_actions(resource, context):
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
        columns = self.get_table_columns(resource, context)
        rows = []
        for item in items:
            row_columns = []
            for column in columns:
                column = column[0]
                # Skip the checkbox column if there are not any actions
                if column == 'checkbox':
                    if not self.external_form and not actions:
                        continue

                value = self.get_item_value(resource, context, item, column)
                column_ns = {
                    'is_checkbox': False,
                    'is_icon': False,
                    'is_link': False,
                }
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
        return {
            'css': self.table_css,
            'columns': table_head,
            'rows': rows,
            'actions': actions,
        }



###########################################################################
# Search View (search + batch + table)
###########################################################################
class SearchForm(BrowseForm):

    template = 'generic/search.xml'

    search_template = 'generic/browse_search.xml'
    search_schema = {
        'search_field': String,
        'search_term': Unicode}
    search_fields =  [
        ('title', MSG(u'Title')),
        ('text', MSG(u'Text')),
        ('name', MSG(u'Name'))]


    def get_query_schema(self):
        return merge_dicts(BrowseForm.get_query_schema(self),
                           self.search_schema)


    def get_search_fields(self, resource, context):
        return self.search_fields


    def get_namespace(self, resource, context):
        namespace = BrowseForm.get_namespace(self, resource, context)

        # The Search Form
        if self.search_template is None:
            namespace['search'] = None
        else:
            search_template = ui.get_template(self.search_template)
            search_namespace = self.get_search_namespace(resource, context)
            namespace['search'] = stl(search_template, search_namespace)

        return namespace


    #######################################################################
    # The Search Form
    def get_search_namespace(self, resource, context):
        # Get values from the query
        field = context.get_query_value('search_field')
        term = context.get_query_value('search_term')

        # Build the namespace
        search_fields = [
            {'name': name, 'title': title, 'selected': name == field}
            for name, title in self.get_search_fields(resource, context) ]

        return {
            'search_term': term,
            'search_fields': search_fields}


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


    def items(self):
        items = self.get_items()
        # Defaults
        for item in items:
            for name in ['class', 'src', 'items']:
                item.setdefault(name, None)

        return items

