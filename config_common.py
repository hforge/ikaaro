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
configuration modules.
"""

# Import from itools
from itools.core import proto_property

# Import from ikaaro
from folder_views import Folder_NewResource



class NewResource_Local(Folder_NewResource):

    @proto_property
    def document_types(self):
        return self.resource.get_document_types()


    include_subclasses = True


    def get_items(self, resource, context):
        # Load dynamic classes
        database = context.database
        list(database.get_dynamic_classes())

        # Case 1: do not include subclasses
        document_types = self.document_types
        if self.include_subclasses is False:
            return document_types

        # Case 2: include subclasses
        root = context.root
        user = context.user

        document_types = tuple(document_types)
        items = []
        for cls in database.get_resource_classes():
            class_id = cls.class_id
            if class_id[0] != '-' and issubclass(cls, document_types):
                if root.has_permission(user, 'add', resource, class_id):
                    items.append(cls)

        return items
