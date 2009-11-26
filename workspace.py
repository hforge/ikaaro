# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import OrderedDict
from itools.gettext import MSG

# Import from ikaaro
from access import AccessControl
from folder import Folder
from user import UserFolder


class Workspace(AccessControl, Folder):

    __fixed_handlers__ = ['users']


    def init_resource(self, **kw):
        super(Workspace, self).init_resource(**kw)
        # User folder
        users = self.make_resource('users', UserFolder, title={'en': u'Users'})


    roles = OrderedDict([
        ('guest', {'title': MSG(u"Guest")}),
        ('member', {'title': MSG(u"Member")}),
        ('reviewer', {'title': MSG(u"Reviewer")}),
        ('admin', {'title': MSG(u'Admin')})])

