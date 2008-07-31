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
from itools.datatypes import Integer, String, Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.web import STLView, STLForm

# Import from ikaaro
from registry import get_object_class


"""This module contains some generic views used by different objects.
"""


class IconsView(STLView):
    """This view draws a menu where each menu item is made up of a big
    icon (48x48 pixels), a title and a description.
    """

    template = '/ui/generic/icons_view.xml.en'

    def get_namespace(self, resource, context):
        """TODO Write a docstring explaining the expected namespace.
        """
        raise NotImplementedError



class NewInstanceForm(STLForm):
    """This is the base class for all ikaaro forms meant to create and
    add a new object to the database.
    """

    def tab_sublabel(self, **kw):
        type = kw.get('type')
        cls = get_object_class(type)
        if cls is not None:
            return cls.class_title.gettext()
        # Default
        return MSG(u'Unknown object.')


    def tab_icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_object_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return '/ui/icons/16x16/new.png'



class BrowseForm(STLForm):

    template = '/ui/generic/browse.xml'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'sortorder': String(default='up'),
        'sortby': String(multiple=True),
        'batchstart': Integer(default=0),
    }

    # [(<name>, <title>), ...]
    search_fields = []


    def search_form(self, resource, query):
        # Get values from the query
        field = query['search_field']
        term = query['search_term']

        # Build the namespace
        namespace = {}
        namespace['search_term'] = term
        namespace['search_fields'] = [
            {'name': name,
             'title': title.gettext(),
             'selected': name == field}
            for name, title in self.search_fields ]

        # Ok
        template = resource.get_object('/ui/generic/browse_search.xml')
        return stl(template, namespace)


    def GET(self, resource, context):
        query = self.get_query(context)

        # Batch / Table
        namespace = self.get_namespace(resource, context, query)
        # Search Form
        namespace['search'] = self.search_form(resource, query)

        # Ok
        template = resource.get_object(self.template)
        return stl(template, namespace)
