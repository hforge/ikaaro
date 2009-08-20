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
from itools.handlers import File
from itools.http import Conflict
from itools.uri import Path
from itools import vfs
from itools.web import WebApplication, lock_body
from itools.web import Resource, BaseView

# Import from ikaaro
from context import CMSContext
from database import get_database
from exceptions import ConsistencyError
from metadata import Metadata
from registry import get_resource_class



class CMSApplication(WebApplication):

    context_class = CMSContext

    def __init__(self, target, size_min, size_max, read_only, index_text):
        self.target = target
        self.database = get_database(target, size_min, size_max, read_only)
        self.index_text = index_text


    def get_context(self, soup_message, path):
        context = WebApplication.get_context(self, soup_message, path)
        context.database = self.database
        context.message = None
        context.content_type = None
        return context


    #######################################################################
    # API
    #######################################################################
    def get_resource(self, path, soft=False):
        if type(path) is not Path:
            path = Path(path)

        # Load metadata
        path = '%s/database/%s.metadata' % (self.target, path)
        try:
            metadata = self.database.get_handler(path, cls=Metadata)
        except LookupError:
            if soft is False:
                raise
            return None
        # Build resource
        cls = get_resource_class(metadata.format)
        resource = cls(metadata)
        resource.path = path
        return resource


    def change_resource(self, resource):
        self.database.change_resource(resource)


    #######################################################################
    # Override WebApplication
    #######################################################################
    def get_host(self, context):
        # Check we have a URI
        uri = context.uri
        if uri is None:
            return self.get_resource('/')

        # The site root depends on the host
        hostname = context.hostname
        results = self.database.catalog.search(vhosts=hostname)
        if len(results) == 0:
            return self.get_resource('/')

        documents = results.get_documents()
        path = documents[0].abspath
        return root.get_resource(path)


    def get_user(self, credentials):
        username, password = credentials
        user = self.get_resource('/users/%s' % username, soft=True)
        if user and user.authenticate(password):
            return user
        return None


    #######################################################################
    # Request methods
    #######################################################################
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
        cut, paths = context.get_cookie('ikaaro_cp', datatype=CopyCookie)
        # Clean cookie
        if str(resource.get_abspath()) in paths:
            context.del_cookie('ikaaro_cp')


    def http_lock(self, context):
        # FIXME access = 'is_allowed_to_lock'
        resource = context.resource
        lock = resource.lock()

        # TODO move in the request handler
        context.content_type = 'text/xml; charset="utf-8"'
        context.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)
        return lock_body % {'owner': context.user.name, 'locktoken': lock}


    def http_unlock(self, context):
        resource = context.resource
        lock = resource.get_lock()
        resource.unlock()

        # TODO move in the request handler
        context.content_type = 'text/xml; charset="utf-8"'
        context.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)

