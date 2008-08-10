# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from operator import itemgetter
from string import Template

# Import from itools
from itools.datatypes import XMLAttribute
from itools.gettext import MSG
from itools.stl import stl
from itools.uri import Path
from itools.web import get_context
from itools.xml import XMLParser

# Import from ikaaro
from utils import get_parameters
from base import DBObject
from folder import Folder
from binary import Image
from utils import reduce_string


namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://xml.itools.org/namespaces/stl'}


###########################################################################
# Table
###########################################################################



def batch(uri, start, size, total, msgs=None):
    """Outputs an HTML snippet with navigation links to move through a set
    of objects.

    Input data:

        uri -- The base URI to use to build the navigation links.

        start -- The start of the batch (from 0).

        size -- The size of the batch.

        total -- The total number of objects.
    """
    # FIXME Use plural forms
    if msgs is None:
        msgs = (
            MSG(u"There is 1 item."),
            MSG(u"There are ${n} items.")
        )

    if total == 1:
        # Singular
        msg1 = msgs[0].gettext()
    else:
        # Plural
        msg1 = msgs[1].gettext(n=total)

    # Calculate end
    end = min(start + size, total)

    # Previous
    previous = None
    if start > 0:
        previous = max(start - size, 0)
        previous = str(previous)
        previous = uri.replace(batchstart=previous)
        previous = str(previous)
        previous = XMLAttribute.encode(previous)
        previous = '<a href="%s" title="%s">&lt;&lt;</a>' \
                   % (previous, MSG(u'Previous').gettext())
    # Next
    next = None
    if end < total:
        next = str(end)
        next = uri.replace(batchstart=next)
        next = str(next)
        next = XMLAttribute.encode(next)
        next = '<a href="%s" title="%s">&gt;&gt;</a>' \
               % (next, MSG(u'Next').gettext())

    # Output
    if previous is None and next is None:
        msg = msg1
    else:
        # View more
        if previous is None:
            link = next
        elif next is None:
            link = previous
        else:
            link = '%s %s' % (previous, next)

        msg2 = MSG(u"View from ${start} to ${end} (${link}):")
        msg2 = msg2.gettext(start=(start+1), end=end, link=link)

        msg = '%s %s' % (msg1, msg2)

    # Wrap around a paragraph
    msg = msg.encode('utf-8')
    return XMLParser('<p class="batchcontrol">%s</p>' % msg, namespaces)



def table_sortcontrol(column, sortby, sortorder):
    """Returns an html snippet with a link that lets to order a column in a
    table.
    """
    # Process column
    if isinstance(column, (str, unicode)):
        column = [column]

    # Calculate the href
    data = {}
    data['sortby'] = column

    if sortby == column:
        value = sortorder
        if sortorder == 'up':
            data['sortorder'] = 'down'
        else:
            data['sortorder'] = 'up'
    else:
        value = 'none'
        data['sortorder'] = 'up'

    href = get_context().uri.replace(**data)
    return href, value


def table_head(columns, sortby, sortorder):
    # Build the namespace
    columns_ = []
    for name, title in columns:
        if title is None:
            column = None
        else:
            column = {'title': title}
            href, sort = table_sortcontrol(name, sortby, sortorder)
            column['href'] = href
            column['order'] = sort
        columns_.append(column)
    # Go
    return columns_

table_with_form_template = list(XMLParser("""
<form action="" method="post" id="browse_list" name="browse_list">
  ${table}
</form>
""", namespaces))

table_template = list(XMLParser("""
<table class="${css}">
  <thead stl:if="columns">
    <tr>
      <th stl:if="column_checkbox" class="checkbox">
        <input type="checkbox" title="Click to select/unselect all rows"
          onclick="select_checkboxes('browse_list', this.checked);" />
      </th>
      <th stl:if="column_image"></th>
      <th stl:repeat="column columns">
        <a stl:if="column" href="${column/href}"
          class="sort_${column/order}">${column/title}</a>
      </th>
    </tr>
  </thead>
  <tbody>
    <tr stl:repeat="row rows" class="${repeat/row/even} ${row/class}">
      <td stl:if="column_checkbox">
        <input class="checkbox" type="checkbox" name="ids" stl:if="row/id"
          value="${row/id}" checked="${row/checked}" />
      </td>
      <td stl:if="column_image">
        <img border="0" src="${row/img}" stl:if="row/img" />
      </td>
      <td stl:repeat="column row/columns">
        <a stl:if="column/href" href="${column/href}">${column/value}</a>
        <stl:block stl:if="not column/href">${column/value}</stl:block>
      </td>
    </tr>
  </tbody>
</table>
<p stl:if="actions">
  <stl:block stl:repeat="action actions">
    <input type="submit" name=";${action/name}" value="${action/value}"
      class="${action/class}" onclick="${action/onclick}" />
  </stl:block>
</p>
""", namespaces))


def table(columns, rows, sortby, sortorder, actions=[], table_with_form=True,
          css=None):
    """The parameters are:

      columns --
        [(name, title), (name, title), ...]

      rows --
        [{'checkbox': , 'img': }, ...]

      sortby --
        The column to sort.

      sortorder --
        The order the column must be sorted by.

      actions --
        [{'name': , 'value': , 'class': , 'onclick': }, ...]
    """
    namespace = {}
    namespace['column_checkbox'] = False
    namespace['column_image'] = False
    # The columns
    namespace['columns'] = table_head(columns, sortby, sortorder)
    # The rows
    aux = []
    for row in rows:
        x = {}
        # The checkbox column
        # TODO Instead of the parameter 'checked', use only 'checkbox', but
        # with three possible values: None, False, True
        id = None
        if row.get('checkbox') is True:
            id = row['id']
            if isinstance(id, tuple):
                id = id[0]
            if isinstance(id, int):
                id = str(id)
            namespace['column_checkbox'] = True
            # Checked by default?
            x['checked'] = row.get('checked', False)
        x['id'] = id
        # The image column
        x['img'] = row.get('img')
        if x['img'] is not None:
            namespace['column_image'] = True
        # A CSS class on the TR
        x['class'] = row.get('class')
        # Other columns
        x['columns'] = []
        for column, kk in columns:
            value = row.get(column)
            if isinstance(value, tuple):
                value, href = value
            else:
                href = None
            x['columns'].append({'value': value, 'href': href})
        aux.append(x)

    namespace['rows'] = aux
    namespace['css'] = css
    # The actions
    namespace['actions'] = [
        {'name': name, 'value': value, 'class': cls, 'onclick': onclick}
        for name, value, cls, onclick in actions ]
    if table_with_form:
        table = {'table': table_template}
        events = stl(events=table_with_form_template, namespace=table)
    else:
        events = table_template

    return stl(events=events, namespace=namespace)



###########################################################################
# Breadcrumb
###########################################################################
class Breadcrumb(object):
    """Instances of this class will be used as namespaces for STL templates.
    The built namespace contains the breadcrumb, that is to say, the path from
    the tree root to another tree node, and the content of that node.
    """

    def __init__(self, filter_type=DBObject, root=None, start=None,
            icon_size=16):
        """The 'start' must be a handler, 'filter_type' must be a handler
        class.
        """
        context = get_context()
        request, response = context.request, context.response

        here = context.resource
        if root is None:
            root = here.get_site_root()
        if start is None:
            start = root

        # Get the query parameters
        parameters = get_parameters('bc', id=None, target=None)
        id = parameters['id']
        # Get the target folder
        target_path = parameters['target']
        if target_path is None:
            if isinstance(start, Folder):
                target = start
            else:
                target = start.parent
        else:
            target = root.get_object(target_path)
        self.target_path = str(target.get_abspath())

        # Object to link
        object = request.get_parameter('object')
        if object == '':
            object = '.'
        self.object = object

        # The breadcrumb
        breadcrumb = []
        node = target
        while node is not root.parent:
            url = context.uri.replace(bc_target=str(root.get_pathto(node)))
            title = node.get_title()
            breadcrumb.insert(0, {'name': node.name,
                                  'title': title,
                                  'short_title': reduce_string(title, 12, 40),
                                  'url': url})
            node = node.parent
        self.path = breadcrumb

        # Content
        objects = []
        self.is_submit = False
        user = context.user
        filter = (Folder, filter_type)
        for object in target.search_objects(object_class=filter):
            ac = object.get_access_control()
            if not ac.is_allowed_to_view(user, object):
                continue

            path = here.get_pathto(object)
            bc_target = str(root.get_pathto(object))
            url = context.uri.replace(bc_target=bc_target)

            self.is_submit = True
            # Calculate path
            path_to_icon = object.get_object_icon(icon_size)
            if path:
                path_to_object = Path(str(path) + '/')
                path_to_icon = path_to_object.resolve(path_to_icon)
            title = object.get_title()
            objects.append({'name': object.name,
                            'title': title,
                            'short_title': reduce_string(title, 12, 40),
                            'is_folder': isinstance(object, Folder),
                            'is_image': isinstance(object, Image),
                            'is_selectable': True,
                            'path': path,
                            'url': url,
                            'icon': path_to_icon,
                            'object_type': object.handler.get_mimetype()})

        objects.sort(key=itemgetter('is_folder'), reverse=True)
        self.objects = objects

        # Avoid general template
        response.set_header('Content-Type', 'text/html; charset=UTF-8')



###########################################################################
# Menu
###########################################################################
menu_template = list(XMLParser("""
<dl>
<stl:block stl:repeat="item items">
  <dt class="${item/class}">
    <img stl:if="item/src" src="${item/src}" alt="" width="16" height="16" />
    <stl:block stl:if="not item/href">${item/title}</stl:block>
    <a stl:if="item/href" href="${item/href}">${item/title}</a>
  </dt>
  <dd>${item/items}</dd>
</stl:block>
</dl>
""", namespaces))



def build_menu(options):
    """The input (options) is a tree:

      [{'href': ...,
        'class': ...,
        'src': ...,
        'title': ...,
        'items': [....]}
       ...
       ]

    """
    for option in options:
        # Defaults
        for name in ['class', 'src', 'items']:
            option.setdefault(name, None)
        # Submenu
        if option['items']:
            option['items'] = build_menu(option['items'])

    namespace = {'items': options}
    return stl(events=menu_template, namespace=namespace)

