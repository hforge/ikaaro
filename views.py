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
from itools.datatypes import Boolean, Integer, String, Unicode
from itools.gettext import MSG
from itools.handlers import merge_dics
from itools.stl import stl
from itools.uri import Path
from itools.web import BaseView, STLView, STLForm, get_context
from itools.xml import XMLParser

# Import from ikaaro
from registry import get_resource_class


"""This module contains some generic views used by different resources.
"""


class MessageView(STLView):

    template = '/ui/generic/message_view.xml'

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

    template = '/ui/generic/icons_view.xml'

    def get_namespace(self, resource, context):
        """TODO Write a docstring explaining the expected namespace.
        """
        raise NotImplementedError



class NewInstanceForm(STLForm):
    """This is the base class for all ikaaro forms meant to create and
    add a new resource to the database.
    """

    def icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_resource_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return 'new.png'


###########################################################################
# Browse View (batch + table)
###########################################################################
class BrowseForm(STLForm):

    template = '/ui/generic/browse.xml'

    query_schema = {
        'batch_start': Integer(default=0),
        'batch_size': Integer(default=20),
        'sort_by': String,
        'reverse': Boolean(default=False),
    }

    # Batch
    batch_template = '/ui/generic/browse_batch.xml'
    batch_msg1 = MSG(u"There is 1 item.") # FIXME Use plural forms
    batch_msg2 = MSG(u"There are ${n} items.")

    # Content
    table_template = '/ui/generic/browse_table.xml'
    table_css = None
    table_columns = []


    def get_namespace(self, resource, context):
        batch = None
        table = None
        # Batch
        items = self.get_items(resource, context)
        if self.batch_template is not None:
            template = resource.get_resource(self.batch_template)
            namespace = self.get_batch_namespace(resource, context, items)
            batch = stl(template, namespace)

        # Content
        items = self.sort_and_batch(resource, context, items)
        if self.table_template is not None:
            template = resource.get_resource(self.table_template)
            namespace = self.get_table_namespace(resource, context, items)
            table = stl(template, namespace)

        return {'batch': batch, 'table': table}


    #######################################################################
    # Private API (to override)
    def get_table_columns(self, resource, context):
        return self.table_columns


    def get_items(self, resource, context):
        name = 'get_items'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def sort_and_batch(self, resource, context, items):
        name = 'sort_and_batch'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def get_item_value(self, resource, context, item, column):
        name = 'get_item_value'
        raise NotImplementedError, "the '%s' method is not defined" % name


    def get_actions(self, resource, context, items):
        name = 'get_actions'
        raise NotImplementedError, "the '%s' method is not defined" % name


    #######################################################################
    # Batch
    def get_batch_namespace(self, resource, context, items):
        start = context.query['batch_start']
        size = context.query['batch_size']
        namespace = {}
        namespace['control'] = False

        # Message (singular or plural)
        total = len(items)
        if total == 1:
            namespace['msg'] = self.batch_msg1.gettext()
        else:
            namespace['msg'] = self.batch_msg2.gettext(n=total)

        # Start & End
        end = min(start + size, total)
        namespace['start'] = start + 1
        namespace['end'] = end

        # Previous
        uri = context.uri
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
    def get_table_namespace(self, resource, context, items):
        # Get from the query
        query = context.query
        sort_by = query['sort_by']
        reverse = query['reverse']

        # (1) Actions (submit buttons)
        actions = self.get_actions(resource, context, items)
        actions = [
            {'name': name, 'value': value, 'class': cls, 'onclick': onclick}
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
                columns_ns.append({'is_checkbox': False, 'href': None})
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
            row_columns = []
            for column, column_title in columns:
                # Skip the checkbox column if there are not any actions
                if column == 'checkbox' and not actions:
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
            rows.append({
                'columns': row_columns,
            })

        # Ok
        return {
            'css': self.table_css,
            'columns': columns_ns,
            'rows': rows,
            'actions': actions,
        }



###########################################################################
# Search View (search + batch + table)
###########################################################################
class SearchForm(BrowseForm):

    template = '/ui/generic/search.xml'

    search_template = '/ui/generic/browse_search.xml'
    search_schema = {
        'search_field': String,
        'search_term': Unicode,
    }
    search_fields =  [
        ('title', MSG(u'Title')),
        ('text', MSG(u'Text')),
        ('name', MSG(u'Name')),
    ]


    def get_query_schema(self):
        return merge_dics(BrowseForm.get_query_schema(self),
                          self.search_schema)


    def get_search_fields(self, resource, context):
        return self.search_fields


    def get_namespace(self, resource, context):
        namespace = BrowseForm.get_namespace(self, resource, context)

        # The Search Form
        if self.search_template is None:
            namespace['search'] = None
        else:
            search_template = resource.get_resource(self.search_template)
            search_namespace = self.get_search_namespace(resource, context)
            namespace['search'] = stl(search_template, search_namespace)

        return namespace


    #######################################################################
    # The Search Form
    def get_search_namespace(self, resource, context):
        # Get values from the query
        query = context.query
        field = query['search_field']
        term = query['search_term']

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
class ContextMenu(object):

    template = '/ui/generic/menu.xml'

    def get_items(self, resource, context):
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


    def get_namespace(self, resource, context):
        items = self.get_items(resource, context)
        # Defaults
        for item in items:
            for name in ['class', 'src', 'items']:
                item.setdefault(name, None)

        return {
            'title': self.title,
            'items': items}


    def render(self, resource, context):
        namespace = self.get_namespace(resource, context)
        template = resource.get_resource(self.template)
        return stl(template, namespace)

