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
from itools.core import get_abspath, lazy, merge_dicts
from itools.handlers import ConfigFile, ro_database
from itools.uri import Path
from itools.web import WebContext, lock_body
from itools.xapian import AllQuery, AndQuery, NotQuery, PhraseQuery, OrQuery
from itools.xapian import StartQuery
from itools.xapian import SearchResults

# Import from ikaaro
from ikaaro.globals import spool, ui
from folder import Folder
from metadata import Metadata
from registry import get_resource_class


class CMSContext(WebContext):

    def __init__(self, soup_message, path):
        super(CMSContext, self).__init__(soup_message, path)

        # Cache for searches
        self._search_cache = {}

        # The resources that been added, removed, changed and moved can be
        # represented as a set of two element tuples.  But we implement this
        # with two dictionaries (old2new/new2old), to be able to access any
        # "tuple" by either value.  With the empty tuple we represent the
        # absence of change.
        #
        #  Tuple        Description                Implementation
        #  -----------  -------------------------  -------------------
        #  ()           nothing has been done yet  {}/{}
        #  (None, 'b')  resource 'b' added         {}/{'b':None}
        #  ('b', None)  resource 'b' removed       {'b':None}/{}
        #  ('b', 'b')   resource 'b' changed       {'b':'b'}/{'b':'b'}
        #  ('b', 'c')   resource 'b' moved to 'c'  {'b':'c'}/{'c':'b'}
        #
        # In real life, every value is either None or an absolute path (as a
        # byte stringi).  For the description that follows, we use the tuples
        # as a compact representation.
        #
        # There are four operations:
        #
        #  A(b)   - add "b"
        #  R(b)   - remove "b"
        #  C(b)   - change "b"
        #  M(b,c) - move "b" to "c"
        #
        # Then, the algebra is:
        #
        # ()        -> A(b) -> (None, 'b')
        # (b, None) -> A(b) -> (b, b)
        # (None, b) -> A(b) -> error
        # (b, b)    -> A(b) -> error
        # (b, c)    -> A(b) -> (b, b), (None, c) FIXME Is this correct?
        #
        # TODO Finish
        #
        self.cache = {}
        self.cache_old2new = {}
        self.cache_new2old = {}


    def get_template(self, path):
        return ui.get_template(path)


    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False, attachment=None):

        # From address
        site_root = self.site_root
        if from_addr is None:
            user = self.user
            if user is None:
                username = site_root.get_property('emails_from_addr')
                if username:
                    user = self.get_user_by_name(username)

            if user:
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


    def get_physical_root(self):
        database = self.mount.database
        metadata = '%s/database/.metadata' % self.mount.target
        metadata = database.get_handler(metadata, cls=Metadata)
        cls = get_resource_class(metadata.format)
        return cls(metadata)


    @lazy
    def software_languages(self):
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
        self.change_resource(resource)
        self.no_content()


    def http_delete(self):
        self.commit = True
        # FIXME access = 'is_allowed_to_remove'
        resource = self.resource
        name = resource.get_name()
        parent = resource.get_parent()
        try:
            parent.del_resource(name)
        except ConsistencyError:
            raise ClientError(409)

        # Clean the copy cookie if needed
        cut, paths = self.get_cookie('ikaaro_cp', datatype=CopyCookie)
        # Clean cookie
        if str(resource.path) in paths:
            self.del_cookie('ikaaro_cp')
        self.no_content()


    def http_lock(self):
        self.commit = True
        # FIXME access = 'is_allowed_to_lock'
        resource = self.resource
        lock = resource.lock()

        self.set_header('Lock-Token', 'opaquelocktoken:%s' % lock)
        body = lock_body % {'owner': self.user.get_name(), 'locktoken': lock}
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

        documents = SearchResults.get_documents(results)
        return documents[0].name


    def _get_metadata(self, key, path):
        target = self.mount.target
        host = self.host
        if not host:
            physical_path = '%s/database%s.metadata' % (target, key)
        elif path:
            physical_path = '%s/database/%s%s.metadata' % (target, host, key)
        else:
            physical_path = '%s/database/%s.metadata' % (target, host)

        return self.mount.database.get_handler(physical_path, cls=Metadata)


    def _get_resource(self, key, path):
        try:
            metadata = self._get_metadata(key, path)
        except LookupError:
            return None
        cls = get_resource_class(metadata.format)
        return cls(metadata=metadata)


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

        # Lookup the resource
        old2new = self.cache_old2new
        if key in old2new and old2new[key] != key:
            resource = None
        else:
            resource = self._get_resource(key, path)

        # Miss
        if resource is None:
            if soft:
                return None
            raise LookupError, 'resource "%s" not found' % key

        # Hit
        resource.context = self
        resource.path = path
        self.cache[key] = resource
        return resource


    def del_resource(self, path, soft=False):
        # (1) Get the resource to remove
        resource = self.get_resource(path, soft=soft)
        if soft and resource is None:
            return

        # (2) Check referencial-integrity
        database = self.database
        # FIXME Check sub-resources too
        physical_path = str(resource.physical_path)
        results = database.catalog.search(links=physical_path)
        if len(results):
            message = 'cannot delete, resource "%s" is referenced' % path
            raise ConsistencyError, message

        # (3) Update cache
        old2new = self.cache_old2new
        new2old = self.cache_new2old
        if issubclass(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.path)
                old2new[path] = None
                new2old.pop(path, None)
                del self.cache[path]
        else:
            path = str(resource.path)
            old2new[path] = None
            new2old.pop(path, None)
            del self.cache[path]

        # (4) Remove
        fs = database.fs
        for handler in resource.get_handlers():
            # Skip empty folders and phantoms
            if fs.exists(handler.key):
                database.del_handler(handler.key)
        database.del_handler(resource.metadata.key)


    def add_resource(self, resource):
        old2new = self.cache_old2new
        new2old = self.cache_new2old

        if issubclass(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.path)
                self.cache[path] = x
                new2old[path] = None
        else:
            path = str(resource.path)
            self.cache[path] = resource
            new2old[path] = None


    def change_resource(self, resource):
        old2new = self.cache_old2new
        new2old = self.cache_new2old

        path = str(resource.path)
        if path in old2new and not old2new[path]:
            raise ValueError, 'cannot change a resource that has been removed'

        if path not in new2old:
            old2new[path] = path
            new2old[path] = path


    def move_resource(self, source, new_path):
        old2new = self.cache_old2new
        new2old = self.cache_new2old

        def f(source_path, target_path):
            source_path = str(source_path)
            target_path = str(target_path)
            if source_path in old2new and not old2new[source_path]:
                error = 'cannot move a resource that has been removed'
                raise ValueError, error

            # Update double dict
            source_path = new2old.pop(source_path, source_path)
            if source_path:
                old2new[source_path] = target_path
            new2old[target_path] = source_path
            del self.cache[source_path]

        old_path = source.path
        if issubclass(source, Folder):
            for x in source.traverse_resources():
                x_old_path = x.path
                x_new_path = new_path.resolve2(old_path.get_pathto(x_old_path))
                f(x_old_path, x_new_path)
        else:
            f(old_path, new_path)


    #######################################################################
    # Search
    #######################################################################
    def get_root_search(self, root='/', included=True):
        if type(root) is Path:
            root = str(root)

        # Hit
        cache = self._search_cache
        key = (root, included)
        if key in cache:
            return cache[key]

        # Miss
        phypath = '/%s%s' % (self.host, root) if self.host else root
        if phypath == '/':
            if included:
                # Case 1: everything
                query = AllQuery()
            else:
                # Case 2: everything but the root
                query = NotQuery(PhraseQuery('abspath', '/'))
        else:
            # Case 3: some sub-folder
            if phypath[-1] != '/':
                phypath += '/'
            query = StartQuery('abspath', phypath)
            if included:
                container = PhraseQuery('abspath', phypath[:-1])
                query = OrQuery(container, query)

        search = self.database.catalog.search(query)
        cache[key] = search
        return search


    def search(self, query=None, **kw):
        results = self.get_root_search()
        return results.search(query, **kw)


    def abort_changes(self):
        self.database.abort_changes()
        self.database._cleanup()
        self.cache_old2new.clear()
        self.cache_new2old.clear()


    def save_changes(self):
        cache = self.cache

        # Update links when resources moved
        for source, target in self.cache_old2new.items():
            if target and source != target:
                cache[target]._on_move_resource(source)

        # Index
        docs_to_unindex = self.cache_old2new.keys()
        docs_to_index = [ cache[x] for x in self.cache_new2old ]

        # Versioning / Author
        user = self.user
        if user:
            email = user.get_value('email')
            git_author = '%s <%s>' % (user.get_name(), email)
        else:
            git_author = 'nobody <>'
        # Versioning / Message
        try:
            git_message = getattr(self, 'git_message')
        except AttributeError:
            git_message = "%s %s" % (self.soup_message.get_method(), self.uri)
        else:
            git_message = git_message.encode('utf-8')

        # Save
        data = git_author, git_message, docs_to_index, docs_to_unindex
        self.database.save_changes(data)
        self.database._cleanup()
        self.cache_old2new.clear()
        self.cache_new2old.clear()


    #######################################################################
    # Shared Users database
    #######################################################################
    def get_shared_user_by_email(self, email):
        query = AndQuery(
            StartQuery('abspath', '/users/'),
            PhraseQuery('format', 'user'),
            PhraseQuery('email', email))
        results = self.database.catalog.search(query)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = (
                u'There are %s users in the shared database with the "%s" '
                u'email address')
            raise ValueError, error % (n, login)
        brains = SearchResults.get_documents(results)
        return brain[0]


    def make_shared_user(self):
        # (1) Find out user name
        database = self.mount.database
        path = '%s/database/users' % self.mount.target
        new_name = 0
        for name in database.get_handler_names(path):
            if name.endswith('.metadata'):
                name = name[:-9]
                if name.isdigit():
                    name = int(name)
                    if name >= new_name:
                        new_name = name + 1
        name = str(new_name)

        # (2) Make the metadata
        path = '%s/%s.metadata' % (path, name)
        cls = get_resource_class('user')
        metadata = Metadata(cls=cls)
        database.set_handler(path, metadata)

        # (3) Get the resource
        resource = cls(metadata=metadata)

        path = Path('/users/%s' % name)
        key = str(path)
        if self.host:
            resource.physical_path = path
            key = '..%s' % key # FIXME Hack
        else:
            resource.path = path

        resource.context = self
        self.cache_new2old[key] = None
        self.cache[key] = resource

        # Ok
        return resource


    #######################################################################
    # Shared Users database
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
        results = self.search(format='user', username=login)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, login)
        # Get the user
        resources = results.get_documents()
        return resources.next()


    def get_user_title(self, username):
        if username is None:
            return None
        user = self.get_user_by_name(username)
        return user.get_title() if user else None

