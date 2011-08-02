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
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.stl import stl
from itools.web import STLView
from itools.xml import XMLParser

# Import from ikaaro
from autoform import AutoForm
from buttons import Button
from utils import CMSTemplate


"""This module contains some generic views used by different resources.
"""


class CompositeView(STLView):

    template = '/ui/generic/cascade.xml'
    subviews = []


    def get_styles(self, context):
        styles = getattr(self, 'styles', [])
        for view in self.subviews:
            _get_styles = getattr(view, 'get_styles', None)
            if _get_styles is None:
                extra = getattr(view, 'styles', [])
            else:
                extra = _get_styles(context)
            styles.extend(extra)
        return styles


    def get_scripts(self, context):
        scripts = getattr(self, 'scripts', [])
        for view in self.subviews:
            _get_scripts = getattr(view, 'get_scripts', None)
            if _get_scripts is None:
                extra = getattr(view, 'scripts', [])
            else:
                extra = _get_scripts(context)
            scripts.extend(extra)
        return scripts


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


    def get_allowed_subviews(self, resource, context):
        user = context.user
        ac = resource.get_access_control()
        for view in self.subviews:
            if ac.is_access_allowed(user, resource, view):
                yield view


    def get_schema(self, resource, context):
        # Check for specific schema
        method_name = context.form_action
        for view in self.subviews:
            if getattr(view, method_name, None):
                schema = getattr(view, '%s_schema' % method_name, None)
                if schema is not None:
                    return schema
                return view.get_schema(resource, context)

        return {}


    def get_action(self, resource, context):
        method = super(CompositeView, self).get_action(resource, context)
        if method:
            return method

        # Check subviews
        method_name = context.form_action
        method = None
        for view in self.subviews:
            view_method = getattr(view, method_name, None)
            if method and view_method:
                msg = 'method "%s" should not be defined in several subviews'
                raise ValueError, msg % context.form_action
            method = view_method

        return method


    def get_namespace(self, resource, context):
        # Case 1. GET
        if context.method == 'GET':
            views = self.get_allowed_subviews(resource, context)
            views = [ view.GET(resource, context) for view in views ]
            return {'views': views}

        # Case 2. POST
        # Render the subview which caused the POST as a 'POST' and the others
        # as a 'GET'
        views = []
        for view in self.get_allowed_subviews(resource, context):
            method = getattr(view, context.form_action, None)
            if method is None:
                context.method = 'GET'
                views.append(view.GET(resource, context))
            else:
                # Render the view as if it was a POST
                context.method = 'POST'
                views.append(view.GET(resource, context))

        # Restore context.method
        context.method = 'POST'
        return {'views': views}




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
        """Example:
        return {'batch': None,
                'items': [{'icon': '/ui/..', 'title': ...,
                           'description': ..., 'url': ...'}, ...]}
        """
        raise NotImplementedError



###########################################################################
# Browse View (batch + table + search)
###########################################################################
class BrowseForm(STLView):

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
    batch_msg2 = MSG(u"There are {n} items.")
    batch_max_middle_pages = None

    # Search configuration
    search_schema = {}
    search_widgets = []

    # Content
    table_template = '/ui/generic/browse_table.xml'
    table_css = None
    table_columns = []
    table_actions = []
    # Actions are external to current form
    external_form = False

    # Keep the batch in the canonical URL
    canonical_query_parameters = (STLView.canonical_query_parameters
                                  + ['batch_start'])


    def get_query_schema(self):
        proxy = super(BrowseForm, self)
        return merge_dicts(proxy.get_query_schema(), self.search_schema)


    def get_namespace(self, resource, context):
        batch = None
        table = None
        # Batch
        items = self.get_items(resource, context)
        if self.batch_template is not None:
            template = context.get_template(self.batch_template)
            namespace = self.get_batch_namespace(resource, context, items)
            batch = stl(template, namespace)

        # Content
        items = self.sort_and_batch(resource, context, items)
        if self.table_template is not None:
            template = context.get_template(self.table_template)
            namespace = self.get_table_namespace(resource, context, items)
            table = stl(template, namespace)

        # The Search Form
        search = None
        if self.search_widgets:
            search = self.get_search_namespace(resource, context)

        return {'batch': batch, 'table': table, 'search': search}


    ##################################################
    # Search
    ##################################################
    def get_search_namespace(self, resource, context):
        search_button = Button(access=True,
            resource=resource, context=context,
            css='button-search', title=MSG(u'Search'))
        form = AutoForm(
            title=MSG(u'Search'),
            method='get',
            schema=self.search_schema,
            widgets=self.search_widgets,
            actions=[search_button])
        return form.GET(resource, context)


    #######################################################################
    # Private API (to override)
    def get_table_columns(self, resource, context):
        return self.table_columns


    def _get_table_columns(self, resource, context):
        """ Always return a tuple of 4 elements. """
        table_columns = []
        for column in self.get_table_columns(resource, context):
            if len(column) == 2:
                name, title = column
                column = (name, title, True, None)
            elif len(column) == 3:
                name, title, sortable = column
                column = (name, title, sortable, None)
            table_columns.append(column)
        return table_columns


    def get_items(self, resource, context, *args):
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
        batch_start = context.query['batch_start']
        uri = context.uri

        # Total & Size
        size = context.query['batch_size']
        total = len(items)
        if size == 0:
            nb_pages = 1
            current_page = 1
        else:
            nb_pages = total / size
            if total % size > 0:
                nb_pages += 1
            current_page = (batch_start / size) + 1

        namespace['control'] = nb_pages > 1

        # Message (singular or plural)
        if total == 1:
            namespace['msg'] = self.batch_msg1.gettext()
        else:
            namespace['msg'] = self.batch_msg2.gettext(n=total)

        # See previous button ?
        if current_page != 1:
            previous = max(batch_start - size, 0)
            namespace['previous'] = uri.replace(batch_start=previous)
        else:
            namespace['previous'] = None

        # See next button ?
        if current_page < nb_pages:
            namespace['next'] = uri.replace(batch_start=batch_start+size)
        else:
            namespace['next'] = None

        # Add middle pages
        middle_pages = range(max(current_page - 3, 2),
                             min(current_page + 3, nb_pages-1) + 1)

        # Truncate middle pages if nedded
        if self.batch_max_middle_pages:
            middle_pages_len = len(middle_pages)
            if middle_pages_len > self.batch_max_middle_pages:
                delta = middle_pages_len - self.batch_max_middle_pages
                delta_start = delta_end = delta / 2
                if delta % 2 == 1:
                    delta_end = delta_end +1
                middle_pages = middle_pages[delta_start:-delta_end]

        pages = [1] + middle_pages
        if nb_pages > 1:
            pages.append(nb_pages)

        namespace['pages'] = [
            {'number': i,
             'css': 'current' if i == current_page else None,
             'uri': uri.replace(batch_start=((i-1) * size))}
             for i in pages ]

        # Add ellipsis if needed
        if nb_pages > 5:
            ellipsis = {'uri': None}
            if 2 not in middle_pages:
                namespace['pages'].insert(1, ellipsis)
            if (nb_pages - 1) not in middle_pages:
                namespace['pages'].insert(len(namespace['pages']) - 1,
                                          ellipsis)

        return namespace


    #######################################################################
    # Table
    def get_table_head(self, resource, context, items, actions=None):
        # Get from the query
        query = context.query
        sort_by = query['sort_by']
        reverse = query['reverse']

        columns = self._get_table_columns(resource, context)
        columns_ns = []
        for name, title, sortable, css in columns:
            if name == 'checkbox':
                # Type: checkbox
                if self.external_form or actions:
                    columns_ns.append({'is_checkbox': True})
            elif title is None or not sortable:
                # Type: nothing or not sortable
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'css': 'thead-%s' % name,
                    'href': None,
                    'sortable': False})
            else:
                # Type: normal
                base_href = context.uri.replace(sort_by=name, batch_start=None)
                if name == sort_by:
                    sort_up_active = reverse is False
                    sort_down_active = reverse is True
                else:
                    sort_up_active = sort_down_active = False
                columns_ns.append({
                    'is_checkbox': False,
                    'title': title,
                    'css': 'thead-%s' % name,
                    'sortable': True,
                    'href': context.uri.path,
                    'href_up': base_href.replace(reverse=0),
                    'href_down': base_href.replace(reverse=1),
                    'sort_up_active': sort_up_active,
                    'sort_down_active': sort_down_active
                    })
        return columns_ns


    def get_actions_namespace(self, resource, context, items):
        return [ button(resource=resource, context=context, items=items)
                 for button in self.get_table_actions(resource, context) ]


    def get_table_namespace(self, resource, context, items):
        # (1) Actions (submit buttons)
        actions = self.get_actions_namespace(resource, context, items)
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
            'external_form': self.external_form or not actions}



###########################################################################
# Menu
###########################################################################
class ContextMenu(CMSTemplate):

    template = '/ui/generic/menu.xml'

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

