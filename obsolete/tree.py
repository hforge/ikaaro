# -*- coding: UTF-8 -*-
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 Hervé Cauwelier <herve@itaapy.com>
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


def _tree(node, root, depth, active_node, allow, deny, user, width):
    # Build the namespace
    namespace = {}
    namespace['src'] = node.get_class_icon()
    namespace['title'] = node.get_title()

    # The href
    view = node.get_view(None)
    if view is None:
        namespace['href'] = None
    else:
        path = root.get_pathto(node)
        namespace['href'] = '/' + str(path)

    # The CSS style
    namespace['class'] = ''
    if node.abspath == active_node.abspath:
        namespace['class'] = 'nav_active'

    # Expand only if in path
    aux = active_node
    while True:
        # Match
        if aux.abspath == node.abspath:
            break
        # Reach the root, do not expand
        if aux.abspath == root.abspath:
            namespace['items'] = []
            return namespace, False
        # Next
        aux = aux.parent

    # Expand till a given depth
    if depth <= 0:
        namespace['items'] = []
        return namespace, True

    # Expand the children
    depth = depth - 1

    # Filter the handlers by the given class (don't filter by default)
    search = node.search_objects(object_class=allow)
    if deny is not None:
        search = [ x for x in search if not isinstance(x, deny) ]

    children = []
    counter = 0
    for child in search:
        ac = child.get_access_control()
        if ac.is_allowed_to_view(user, child):
            ns, in_path = _tree(child, root, depth, active_node, allow, deny,
                                user, width)
            if in_path:
                children.append(ns)
            elif counter < width:
                children.append(ns)
            counter += 1
    if counter > width:
        children.append({'href': None,
                         'class': '',
                         'src': None,
                         'title': '...',
                         'items': []})
    namespace['items'] = children

    return namespace, True



def tree(root, depth=6, active_node=None, allow=None, deny=None, user=None,
         width=10):
    ns, kk = _tree(root, root, depth, active_node, allow, deny, user, width)
    return build_menu([ns])

