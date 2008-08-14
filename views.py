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
from itools.xml import XMLParser

# Import from ikaaro
from registry import get_object_class
from widgets import batch, table


"""This module contains some generic views used by different objects.
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
    add a new object to the database.
    """

    def icon(self, resource, **kw):
        type = kw.get('type')
        cls = get_object_class(type)
        if cls is not None:
            return cls.get_class_icon()
        # Default
        return 'new.png'



class BrowseForm(STLForm):

    template = '/ui/generic/browse.xml'

    query_schema = {
        'search_field': String,
        'search_term': Unicode,
        'sortorder': String(default='up'),
        'sortby': String(multiple=True),
        'batchstart': Integer(default=0),
    }

    def GET(self, resource, context):
        # Check there is a template defined
        if self.template is None:
            raise NotImplementedError

        # Load the query
        context.query = self.get_query(context)

        # Search
        results = self.search(resource, context)

        # Get the namespace
        namespace = {
            'search': self.search_form(resource, context),
            'batch': self.get_batch(results, context),
            'table': self.get_table(resource, context, results),
        }

        # Ok
        template = resource.get_resource(self.template)
        return stl(template, namespace)


    #######################################################################
    # Search Form
    #######################################################################
    search_fields = [] # [(<name>, <title>), ...]

    def search_form(self, resource, context):
        # Get values from the query
        query = context.query
        field = query['search_field']
        term = query['search_term']

        # Build the namespace
        search_fields = [
            {'name': name, 'title': title.gettext(),
             'selected': name == field}
            for name, title in self.search_fields ]
        namespace = {
            'search_term': term,
            'search_fields': search_fields}

        # Ok
        template = resource.get_resource('/ui/generic/browse_search.xml')
        return stl(template, namespace)


    def search(self, resource, context):
        return []


    #######################################################################
    # Batch
    #######################################################################
    batchsize = 20

    def get_batch(self, results, context):
        query = context.query
        start = query['batchstart']
        size = self.batchsize
        total = len(results)

        return batch(context.uri, start, size, total)


    #######################################################################
    # Table
    #######################################################################
    columns = []
    actions = []


    def get_columns(self, resource, context):
        return self.columns


    def get_actions(self, resource, context):
        return self.actions


    def get_table(self, resource, context, results):
        columns = self.get_columns(resource, context)
        rows = self.get_rows(resource, context, results)
        sortby = context.query['sortby']
        sortorder = context.query['sortorder']
        actions = self.get_actions(resource, context, results)
        return table(columns, rows, sortby, sortorder, actions)
