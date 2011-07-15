# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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
from itools.web import AccessControl as BaseAccessControl

# Import from ikaaro
from workflow import WorkflowAware



###########################################################################
# Utility
###########################################################################
def is_admin(user, resource):
    if user is None or resource is None:
        return False

    if (resource.get_site_root().get_abspath() !=
        user.get_site_root().get_abspath()):
        return False

    return 'admins' in user.get_property('groups')



###########################################################################
# Model
###########################################################################
class AccessControl(BaseAccessControl):

    def is_admin(self, user, resource):
        return is_admin(user, resource)


    def is_owner_or_admin(self, user, resource):
        if user is None:
            return False
        if self.is_admin(user, resource):
            return True
        owner = resource.get_owner()
        return owner == user.name


    def is_allowed_to_view(self, user, resource):
        # Resources with workflow
        if isinstance(resource, WorkflowAware):
            state = resource.workflow_state
            # Anybody can see public resources
            if state == 'public':
                return True

            # Only those who can edit are allowed to see non-public resources
            return self.is_allowed_to_edit(user, resource)

        # Everybody can see resources without workflow
        return True


    def is_allowed_to_edit(self, user, resource):
        # By default only the admin can touch stuff
        return self.is_admin(user, resource)


    # By default all other change operations (add, remove, copy, etc.)
    # are equivalent to "edit".
    def is_allowed_to_put(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_add(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_remove(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_copy(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_move(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_trans(self, user, resource, name):
        if not isinstance(resource, WorkflowAware):
            return False

        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_publish(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'publish')


    def is_allowed_to_retire(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'retire')


    def is_allowed_to_view_folder(self, user, resource):
        index = resource.get_resource('index', soft=True)
        if index is None:
            return False
        return self.is_allowed_to_view(user, index)
