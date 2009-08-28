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
from itools.core import get_abspath, merge_dicts
from itools.handlers import ConfigFile, ro_database
from itools.uri import Path
from itools.web import WebContext, lock_body
from itools.xapian import OrQuery, PhraseQuery, StartQuery

# Import from ikaaro
from ikaaro.globals import spool, ui
from metadata import Metadata
from registry import get_resource_class


class CMSContext(WebContext):

    def __init__(self, soup_message, path):
        WebContext.__init__(self, soup_message, path)
        self.cache = {}


    def get_template(self, path):
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


    def load_software_languages(self):
        # Load defaults (ikaaro)
        setup = get_abspath('setup.conf')
        setup = ro_database.get_handler(setup, ConfigFile)
        source = setup.get_value('source_language')
        target = setup.get_value('target_languages')

        # Get the root class
        database = self.mount.database
        metadata = '%s/database/.metadata' % self.mount.target
        metadata = database.get_handler(metadata, cls=Metadata)
        if metadata.format != 'iKaaro':
            # A package based on itools
            cls = get_resource_class(metadata.format)
            exec('import %s as pkg' % cls.__module__.split('.', 1)[0])
            setup = Path(pkg.__path__[0]).resolve_name('setup.conf')
            setup = str(setup)
            setup = ro_database.get_handler(setup, ConfigFile)
            source = setup.get_value('source_language', default=source)
            target = setup.get_value('target_languages', default=target)

        # Calculate
        target = target.split()
        if source in target:
            target.remove(source)

        target.insert(0, source)
        return target


    #######################################################################
    # Handle requests
    #######################################################################
    known_methods = merge_dicts(
        WebContext.known_methods,
        PUT='http_put',
        DELETE='http_delete',
        LOCK='http_lock',
        UNLOCK='http_unlock')


    def http_put(self):
        self.commit = True
        # FIXME access = 'is_allowed_to_lock'
        body = self.get_form_value('body')
        resource = self.resource
        resource.handler.load_state_from_string(body)
        self.database.change_resource(resource)
        self.no_content()


    def http_delete(self):
        self.commit = True
        # FIXME access = 'is_allowed_to_remove'
        resource = self.resource
        name = resource.name
        parent = resource.parent
        try:
            parent.del_resource(name)
        except ConsistencyError:
            raise ClientError(409)

        # Clean the copy cookie if needed
        cut, paths = self.get_cookie('ikaaro_cp', datatype=CopyCookie)
        # Clean cookie
        if str(resource.get_abspath()) in paths:
            self.del_cookie('ikaaro_cp')
        self.no_content()


    def http_lock(self):
        self.commit = True
        # FIXME access = 'is_allowed_to_lock'
        resource = self.resource
        lock = resource.lock()

        self.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)
        body = lock_body % {'owner': self.user.name, 'locktoken': lock}
        self.ok('text/xml; charset="utf-8"', body)


    def http_unlock(self):
        self.commit = True
        resource = self.resource
        lock = resource.get_lock()
        resource.unlock()

        self.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)
        self.no_content()


    #######################################################################
    # Host & Resources
    #######################################################################
    def get_host(self, hostname):
        # Check we have a URI
        if hostname is None:
            return None

        # The site root depends on the host
        catalog = self.mount.database.catalog
        results = catalog.search(vhosts=hostname)
        n = len(results)
        if n == 0:
            return None

        documents = results.get_documents()
        return documents[0].name


    def _get_resource(self, key, path, soft):
        # Step 1. Find the physical path to the metadata
        base = '%s/database' % self.mount.target
        if path:
            # Host=whatever, Path=/users[...]
            if path[0] == 'users':
                metadata = '%s%s.metadata' % (base, key)
            # Host=host, Path=/...
            elif self.host:
                metadata = '%s/%s%s.metadata' % (base, self.host, key)
            # Host=None, Path=/...
            else:
                metadata = '%s%s.metadata' % (base, key)
        elif self.host:
            # Host=host, Path=/
            metadata = '%s/%s.metadata' % (base, self.host)
        else:
            # Host=None, Path=/
            metadata = '%s/.metadata' % base

        # Step 2. Load the metadata
        database = self.mount.database
        try:
            metadata = database.get_handler(metadata, cls=Metadata)
        except LookupError:
            if soft is False:
                raise
            return None

        # Step 3. Return the resource
        cls = get_resource_class(metadata.format)
        return cls(metadata)


    def get_resource(self, path, soft=False):
        if type(path) is Path:
            path = str(path)

        # Get the key
        path = Path(path)
        path.endswith_slash = False
        key = str(path)

        # Cache hit
        resource = self.cache.get(key)
        if resource:
            return resource

        resource = self._get_resource(key, path, soft)
        if resource is None:
            return None
        resource.context = self
        resource.path = path
        self.cache[key] = resource
        return resource


    #######################################################################
    # Search
    #######################################################################
    def load__search(self):
        if self.host is None:
            return None

        abspath = '/%s' % self.host
        query = OrQuery(
            PhraseQuery('abspath', abspath),
            StartQuery('abspath', '%s/' % abspath))

        catalog = self.database.catalog
        return catalog.search(query)


    def search(self, query=None, **kw):
        results = self._search
        if results:
            return results.search(query, **kw)

        catalog = self.database.catalog
        return catalog.search(query, **kw)


    #######################################################################
    # Users
    #######################################################################
    def load__users_search(self):
        catalog = self.database.catalog
        return catalog.search(format='user')


    def search_users(self, query=None, **kw):
        results = self._users_search
        return results.search(query, **kw)


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
        results = self.search_users(username=login)
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

