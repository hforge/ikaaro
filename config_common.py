# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

"""
This module contains some utility code shared accross the different
configuration plugins.
"""

# Import from ikaaro
from autoadd import AutoAdd
from database import Database
from folder_views import Folder_NewResource



class NewInstance_Local(AutoAdd):

    fields = ['title']

    automatic_resource_name = False
    def get_new_resource_name(self, form):
        if self.automatic_resource_name:
            return form['container'].make_resource_name()

        return super(NewInstance_Local, self).get_new_resource_name(form)


    def get_container(self, resource, context, form):
        return resource



class NewResource_Local(Folder_NewResource):

    def get_items(self, resource, context):
        # 1. Load dynamic classes
        models = resource.get_resource('/config/models')
        list(models.get_dynamic_classes())

        # 2. The document types
        document_types = tuple(resource.get_document_types())
        return [ cls for cls in Database.resources_registry.values()
                 if issubclass(cls, document_types) ]
