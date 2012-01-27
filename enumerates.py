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
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.web import get_context

# Import from ikaaro
from fields import URI_Field



###########################################################################
# Dynamic enumerates
###########################################################################

class DynamicEnumerate_Datatype(Enumerate):

    resource_path = None
    def get_options(self):
        path = self.resource_path

        context = get_context()
        resource = context.database.get_resource(path)

        # Security filter
        allowed = context.search(parent_paths=path)
        allowed = [ x.name for x in allowed.get_documents() ]
        allowed = set(allowed)

        # Namespace
        options = []
        for name in resource.get_ordered_values():
            if name in allowed:
                option = resource.get_resource(name)
                options.append({'name': str(option.abspath),
                                'value': option.get_title()})

        return options


class DynamicEnumerate_Field(URI_Field):

    datatype = DynamicEnumerate_Datatype
    datatype_keys = URI_Field.datatype_keys + ['resource_path']


###########################################################################
# User Groups
###########################################################################

class UserGroups_Datatype(DynamicEnumerate_Datatype):
    resource_path = '/config/groups'



class Groups_Datatype(UserGroups_Datatype):

    special_groups = [
        {'name': 'everybody', 'value': MSG(u'Everybody')},
        {'name': 'authenticated', 'value': MSG(u'Authenticated')}]


    def get_options(self):
        options = super(Groups_Datatype, self).get_options()
        return self.special_groups + options
