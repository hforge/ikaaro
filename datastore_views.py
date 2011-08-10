# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.datatypes import String
from itools.web import BaseView, get_context
from itools.web import STLView

# Import from ikaaro
from autoadd import AutoAdd


class DataStore_Proxy(STLView):


    def GET(self, resource, context):
        resource = self.get_datastore_resource()
        if resource is None:
            raise ValueError, 'This datastore resource do not exist'
        return self.get_view().GET(resource, context)


    def POST(self, resource, context):
        resource = self.get_datastore_resource()
        if resource is None:
            raise ValueError, 'This datastore resource do not exist'
        return self.get_view().POST(resource, context)


    def get_query_schema(self):
        return merge_dicts(super(DataStore_Proxy, self).get_query_schema(),
                           id=String, view=String)


    def get_datastore_resource(self):
        context = get_context()
        return context.root.get_resource('/datastore/%s' % context.query['id'])


    def get_view(self):
        resource = self.get_datastore_resource()
        view = resource.get_view(get_context().query['view'])
        if view is None:
            raise ValueError, 'This view do not exist'
        return view


    @property
    def access(self):
        return self.get_view().access



class DataStore_AutoAdd(AutoAdd):


    def get_container(self, resource, context, form):
        return resource.get_resource('/datastore')
