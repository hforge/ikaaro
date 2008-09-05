# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.stl import stl
from itools.uri import Path
from itools.xml import XMLParser


namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://xml.itools.org/namespaces/stl'}



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

