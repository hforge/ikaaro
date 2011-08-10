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

# Import from ikaaro
from autoadd import AutoAdd
from views import CompositeView


class DataStore_Proxy(CompositeView):


    def GET(self, resource, context):
        resource = self.get_datastore_resource()
        if resource is None:
            raise ValueError, 'This datastore resource do not exist'
        return super(DataStore_Proxy, self).GET(resource, context)


    def POST(self, resource, context):
        resource = self.get_datastore_resource()
        if resource is None:
            raise ValueError, 'This datastore resource do not exist'
        return super(DataStore_Proxy, self).POST(resource, context)


    def get_query_schema(self):
        return merge_dicts(super(DataStore_Proxy, self).get_query_schema(),
                           id=String, view=String)


    def get_datastore_resource(self):
        context = get_context()
        return context.root.get_resource('/datastore/%s' % context.query['id'])


    def get_view(self):
        query = get_context().query
        view = getattr(self.get_datastore_resource(), query['view'], None)
        if not view or not issubclass(view.__class__, BaseView):
            raise ValueError, 'This view do not exist'
        return view


    @property
    def access(self):
        return self.get_view().access


    @property
    def subviews(self):
        return [self.get_view()]



class DataStore_AutoAdd(AutoAdd):


    def get_container(self, resource, context, form):
        return resource.get_resource('/datastore')
