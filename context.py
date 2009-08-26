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
from itools.uri import Path
from itools.web import WebContext

# Import from ikaaro
from ikaaro.globals import spool
from metadata import Metadata
from registry import get_resource_class


class CMSContext(WebContext):

    def __init__(self, soup_message, path):
        WebContext.__init__(self, soup_message, path)
        self.cache = {}


    def get_host(self, hostname):
        # Check we have a URI
        if hostname is None:
            return self.get_resource('/')

        # The site root depends on the host
        mount = self.mount
        results = mount.database.catalog.search(vhosts=hostname)
        if len(results) == 0:
            return self.get_resource('/')

        documents = results.get_documents()
        path = documents[0].abspath
        return root.get_resource(path)


    def get_resource(self, path, soft=False):
        if type(path) is str:
            key = path
            path = Path(path)
        elif type(path) is Path:
            key = str(path)
        else:
            error = 'path expected to be string or path, got a "%s"'
            raise TypeError, error % type(path)

        # Cache hit
        resource = self.cache.get(key)
        if resource:
            return resource

        # Load metadata
        mount = self.mount
        metadata = '%s/database/%s.metadata' % (mount.target, key)
        try:
            metadata = mount.database.get_handler(metadata, cls=Metadata)
        except LookupError:
            if soft is False:
                raise
            return None

        # Build resource
        cls = get_resource_class(metadata.format)
        resource = cls(metadata)
        resource.context = self
        resource.path = path
        self.cache[key] = resource
        return resource


    def get_template(self, path):
        from ikaaro.boot import ui
        return ui.get_template(path)


    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False, attachment=None):

        # From address
        site_root = self.site_root
        if from_addr is None:
            user = self.user
            if user is not None:
                from_addr = user.get_title(), user.get_property('email')
            elif site_root.get_property('emails_from_addr'):
                user_name = site_root.get_property('emails_from_addr')
                user = self.get_resource('/users/%s' % user_name)
                from_addr = user.get_title(), user.get_property('email')
            else:
                from_addr = self.server.smtp_from

        # Subject
        if subject_with_host:
            subject = u'[%s] %s' % (self.uri.authority, subject)

        # Signature
        if site_root.get_property('emails_signature'):
            text += '\n\n-- \n%s' % site_root.get_property('emails_signature')

        spool.send_email(to_addr, subject, from_addr=from_addr, text=text,
                        html=html, encoding=encoding,
                        return_receipt=return_receipt, attachment=attachment)


    #######################################################################
    # Search
    #######################################################################
    def search(self, query=None, **kw):
        catalog = self.database.catalog
        return catalog.search(query, **kw)


    #######################################################################
    # Users
    #######################################################################
    def get_user(self, credentials):
        username, password = credentials
        user = self.get_user_by_name(username)
        if user and user.authenticate(password):
            return user
        return None


    def get_user_by_name(self, name):
        return self.get_resource('/users/%s' % name, soft=True)


    def get_user_by_login(self, login):
        """Return the user identified by its unique e-mail or username, or
        return None.
        """
        # Search the user by username (login name)
        results = self.search(username=login)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, login)
        # Get the user
        brain = results.get_documents()[0]
        return self.get_user_by_name(brain.name)


    def get_user_title(self, username):
        if username is None:
            return None
        user = self.get_user_by_name(username)
        return user.get_title() if user else None

