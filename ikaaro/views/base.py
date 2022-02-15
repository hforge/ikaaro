# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2015 Nicolas Deram <nicolas@agicia.com>
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
from datetime import datetime
from logging import getLogger
from os.path import basename, getmtime, isfile

# Import from itools
from itools.core import fixed_offset
from itools.fs.common import get_mimetype

# Import from itools
from itools.core import merge_dicts, proto_property, proto_lazy_property
from itools.datatypes import Boolean, Integer, String
from itools.gettext import MSG
from itools.uri import Path
from itools.stl import stl
from itools.web import STLView, NotModified
from itools.web.static import StaticView
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoform import AutoForm
from ikaaro.buttons import Button
from ikaaro.utils import CMSTemplate

log = getLogger("ikaaro.web")


"""This module contains some generic views used by different resources.
"""


def get_view_styles(view, context):
    get = getattr(view, 'get_styles', None)
    if get:
        return get(context)
    return getattr(view, 'styles', [])


def get_view_scripts(view, context):
    get = getattr(view, 'get_scripts', None)
    if get:
        return get(context)
    return getattr(view, 'scripts', [])


class CompositeView(STLView):

    template = '/ui/ikaaro/generic/cascade.xml'
    subviews = []


    def get_styles(self, context):
        styles = []
        for view in self.allowed_subviews:
            for style in get_view_styles(view, context):
                if style not in styles:
                    styles.append(style)

        return styles


    def get_scripts(self, context):
        scripts = []
        for view in self.allowed_subviews:
            for script in get_view_scripts(view, context):
                if script not in scripts:
                    scripts.append(script)

        return scripts


    def get_query_schema(self):
        schema = {}
        for view in self.allowed_subviews:
            view_schema = view.get_query_schema()
            for key in view_schema:
                if key in schema:
                    raise ValueError("query schema key '{}' defined twice".format(key))
                schema[key] = view_schema[key]
        return schema


    @proto_lazy_property
    def allowed_subviews(self):
        resource = self.resource
        context = self.context

        views = []
        for view in self.subviews:
            view = view(resource=resource, context=context) # bind
            if context.is_access_allowed(resource, view):
                views.append(view)
        return views


    def get_schema(self, resource, context):
        # Check for specific schema
        method_name = context.form_action
        for view in self.allowed_subviews:
            if getattr(view, method_name, None):
                schema = getattr(view, '%s_schema' % method_name, None)
                if schema is not None:
                    return schema
                return view.get_schema(resource, context)

        return {}


    def get_action_view(self, context, action_name):
        # Check action on subviews and return view with action
        action_subview = None
        # Look for acion defined on Subviews
        for view in self.allowed_subviews:
            view_method = getattr(view, action_name, None)
            if action_subview and view_method:
                raise ValueError(
                    "method '{}' should not be defined in several subviews".format(context.form_action)
                )
            if view_method:
                action_subview = view

        # Return appropriate view
        if action_subview:
            return action_subview
        return self


    @proto_lazy_property
    def subviews_to_show(self):
        context = self.context
        resource = self.resource
        subviews = self.allowed_subviews

        # Case 1. GET
        if context.method == 'GET':
            return [ (x.GET(resource, context), x) for x in subviews ]

        # Case 2. POST
        # Render the subview which caused the POST as a 'POST' and the others
        # as a 'GET'
        views = []
        for view in subviews:
            method = getattr(view, context.form_action, None)
            context.method = 'GET' if method is None else 'POST'
            views.append((view.GET(resource, context), view))

        # Restore context.method
        context.method = 'POST'
        return views


    def get_namespace(self, resource, context):
        return {'views': [ x[0] for x in self.subviews_to_show ]}



class MessageView(STLView):

    template = '/ui/ikaaro/generic/message_view.xml'

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

    access = 'is_allowed_to_view'
    template = '/ui/ikaaro/generic/icons_view.xml'
    title = MSG('View')

    def get_namespace(self, resource, context):
        """Example:
        return {'batch': None,
                'items': [{'icon': '/ui/..', 'title': ...,
                           'description': ..., 'url': ...'}, ...]}
        """
        items = []
        for x in resource.get_resources():
            kw = {'icon': x.class_icon_css,
                  'url': x.abspath,
                  'description': x.class_description,
                  'title': x.class_title}
            items.append(kw)
        return {'batch': None,
                'items': items}



###########################################################################
# Browse View (batch + table + search)
###########################################################################
class Batch(CMSTemplate):
    """
    Input parameters:
    - total
    """

    template = '/ui/ikaaro/generic/browse_batch.xml'
    batch_msg1 = MSG(u"There is 1 item.") # FIXME Use plural forms
    batch_msg2 = MSG(u"There are {n} items.")


    @proto_lazy_property
    def start(self):
        return self.context.query['batch_start']


    @proto_lazy_property
    def size(self):
        return self.context.query['batch_size']


    @proto_property
    def msg(self):
        total = self.total
        # Singular
        if total == 1:
            return self.batch_msg1.gettext()
        # Plural
        return self.batch_msg2.gettext(n=total)


    @proto_lazy_property
    def nb_pages(self):
        # Size = 0
        size = self.size
        if size == 0:
            return 1

        # Size > 0
        total = self.total
        nb_pages = total // size
        if (total % size) > 0:
            nb_pages += 1
        return nb_pages


    @proto_lazy_property
    def current_page(self):
        # Size = 0
        size = self.size
        if size == 0:
            return 1

        # Size > 0
        return (self.start // size) + 1


    @proto_property
    def control(self):
        return self.nb_pages > 1


    @proto_property
    def previous(self):
        if self.current_page != 1:
            previous = max(self.start - self.size, 0)
            return self.context.uri.replace(batch_start=previous)

        return None


    @proto_property
    def next(self):
        if self.current_page < self.nb_pages:
            next = self.start + self.size
            return self.context.uri.replace(batch_start=next)

        return None


    @proto_property
    def pages(self):
        # Add middle pages
        current_page = self.current_page
        nb_pages = self.nb_pages
        middle_pages = list(range(max(current_page - 3, 2),
                             min(current_page + 3, nb_pages-1) + 1))

        pages = [1] + middle_pages
        if nb_pages > 1:
            pages.append(nb_pages)

        uri = self.context.uri
        pages = [
            {'number': i,
             'css': 'active' if i == current_page else None,
             'uri': uri.replace(batch_start=((i-1) * self.size))}
             for i in pages ]

        # Add ellipsis if needed
        if nb_pages > 5:
            ellipsis = {'uri': None}
            if 2 not in middle_pages:
                pages.insert(1, ellipsis)
            if (nb_pages - 1) not in middle_pages:
                pages.insert(len(pages) - 1, ellipsis)

        return pages



class BrowseForm(STLView):

    template = '/ui/ikaaro/generic/browse.xml'

    query_schema = {
        'batch_start': Integer(default=0),
        'batch_size': Integer(default=20),
        'sort_by': String,
        'reverse': Boolean(default=False)}

    # Batch
    batch = Batch

    # Search configuration
    search_form_id = 'form-search'
    search_form_css = ''
    search_template = '/ui/ikaaro/auto_form.xml'
    search_template_field = '/ui/ikaaro/auto_form_field.xml'
    search_schema = {}
    search_widgets = []

    # Content
    table_template = '/ui/ikaaro/generic/browse_table.xml'
    table_form_id = 'form-table'
    table_css = 'table table-striped table-bordered'
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
        if self.batch is not None:
            total = len(items)
            batch = self.batch(context=context, total=total).render()

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
    def get_search_actions(self, resource, context):
        search_button = Button(access=True,
            resource=resource, context=context,
            css='btn btn-primary', title=MSG('Search'))
        return [search_button]


    def get_search_namespace(self, resource, context):
        form = AutoForm(
            form_id=self.search_form_id,
            form_css=self.search_form_css,
            template=self.search_template,
            template_field=self.search_template_field,
            title=MSG('Search'),
            method='get',
            schema=self.search_schema,
            widgets=self.search_widgets,
            actions=self.get_search_actions(resource, context))
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


    def get_items(self, resource, context):
        name = 'get_items'
        raise NotImplementedError("the 'get_items' method is not defined")


    def sort_and_batch(self, resource, context, items):
        raise NotImplementedError("the 'sort_and_batch' method is not defined")


    def get_item_value(self, resource, context, item, column):
        if column == 'row_css':
            return None

        # Default
        raise ValueError("unexpected '{}'".format(column))


    def get_table_actions(self, resource, context):
        return self.table_actions


    #######################################################################
    # Table
    def get_table_head(self, resource, context, items):
        actions = self.actions_namespace

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
                    'css': 'thead-%s' % name.replace('_', '-'),
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
                    'css': 'thead-%s' % name.replace('_', '-'),
                    'sortable': True,
                    'href': context.uri.path,
                    'href_up': base_href.replace(reverse=0),
                    'href_down': base_href.replace(reverse=1),
                    'sort_up_active': sort_up_active,
                    'sort_down_active': sort_down_active
                    })
        return columns_ns


    @proto_lazy_property
    def actions_namespace(self):
        resource = self.resource
        context = self.context
        items = self._items

        actions = []
        for button in self.get_table_actions(resource, context):
            button = button(resource=resource, context=context, items=items)
            if button.show:
                actions.append(button)

        return actions


    def get_column_css(self, resource, context, column):
        return None


    def get_table_namespace(self, resource, context, items):
        # (1) Actions (submit buttons)
        self._items = items
        actions = self.actions_namespace
        # (2) Table Head: columns
        table_head = self.get_table_head(resource, context, items)

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
                    'css': self.get_column_css(resource, context, column),
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
            # Row css
            row_css = self.get_item_value(resource, context, item, 'row_css')

            # Append
            rows.append({'css': row_css, 'columns': row_columns})

        # Ok
        return {
            'css': self.table_css,
            'form_id': self.table_form_id,
            'columns': table_head,
            'rows': rows,
            'actions': actions,
            'external_form': self.external_form or not actions}



###########################################################################
# Menu
###########################################################################
class ContextMenu(CMSTemplate):

    template = '/ui/ikaaro/generic/menu.xml'

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



class IkaaroStaticView(StaticView):


    def GET(self, resource, context):
        try:
            return self.get_from_template(resource, context)
        except NotModified:
            raise
        except Exception as e:
            # Fallback if the handler cannot be loaded
            msg = 'WARNING: The file {0} contains errors'.format(context.path)
            log.debug(msg, exc_info=True)
            return self.get_fallback(resource, context)


    def get_from_template(self, resource, context):
        # FIXME Check we set the encoding for text files
        path = str(context.path)
        ts = context.server.timestamp
        path = path.replace('/cached/%s' % ts, '')
        template = context.get_template(path)
        # 404 Not Found
        if not template:
            return context.set_default_response(404)
        # 304 Not Modified
        mtime = template.get_mtime()
        mtime = fixed_offset(0).localize(mtime)
        since = context.get_header('If-Modified-Since')
        if since and since >= mtime:
            raise NotModified
        mimetype = template.get_mimetype()
        # Get data
        data = template.to_str()
        # Response
        context.status = 200
        context.set_content_type(mimetype)
        context.set_header('Last-Modified', mtime)
        return data


    def get_fallback(self, resource, context):
        n = len(Path(self.mount_path))
        path = Path(context.path)[n:]
        path = '%s%s' % (self.local_path, path)
        # 404 Not Found
        if not isfile(path):
            return context.set_default_response(404)
        # 304 Not Modified
        mtime = getmtime(path)
        mtime = datetime.utcfromtimestamp(mtime)
        mtime = mtime.replace(microsecond=0)
        mtime = fixed_offset(0).localize(mtime)
        since = context.get_header('If-Modified-Since')
        if since and since >= mtime:
            raise NotModified
        # 200 Ok
        # FIXME Check we set the encoding for text files
        mimetype = get_mimetype(basename(path))
        # Get data
        with open(path, 'r') as f:
            data = f.read()
        # Response
        context.status = 200
        context.set_content_type(mimetype)
        context.set_header('Last-Modified', mtime)
        return data



class CachedStaticView(IkaaroStaticView):

    def GET(self, query, context):
        proxy = super(CachedStaticView, self)
        data = proxy.GET(query, context)
        if context.status == 200:
            context.set_header('Cache-Control', 'max-age=315360000')
        return data
