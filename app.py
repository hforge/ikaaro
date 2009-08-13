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
from itools.http import Conflict
from itools.web import WebApplication, lock_body

# Import from ikaaro
from exceptions import ConsistencyError


class CMSApplication(WebApplication):

    def http_put(self, context):
        # FIXME access = 'is_allowed_to_lock'
        body = context.get_form_value('body')
        resource.handler.load_state_from_string(body)
        context.server.change_resource(resource)


    def http_delete(self, context):
        # FIXME access = 'is_allowed_to_remove'
        resource = context.resource
        name = resource.name
        parent = resource.parent
        try:
            parent.del_resource(name)
        except ConsistencyError:
            raise Conflict

        # Clean the copy cookie if needed
        cut, paths = context.get_cookie('ikaaro_cp', type=CopyCookie)
        # Clean cookie
        if str(resource.get_abspath()) in paths:
            context.del_cookie('ikaaro_cp')


    def http_lock(self, context):
        # FIXME access = 'is_allowed_to_lock'
        resource = context.resource
        lock = resource.lock()

        # TODO move in the request handler
        context.set_header('Content-Type', 'text/xml; charset="utf-8"')
        context.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)
        return lock_body % {'owner': context.user.name, 'locktoken': lock}


    def http_unlock(self, context):
        resource = context.resource
        lock = resource.get_lock()
        resource.unlock()

        # TODO move in the request handler
        context.set_header('Content-Type', 'text/xml; charset="utf-8"')
        context.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)

