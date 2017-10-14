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

# Import from standard library
from copy import deepcopy

# Import from itools
from itools.database import RWDatabase, RODatabase as BaseRODatabase
from itools.database import OrQuery, PhraseQuery, AndQuery
from itools.uri import Path
from itools.web import get_context, set_context


class RODatabase(BaseRODatabase):

    def init_context(self):
        from ikaaro.context import CMSContext
        root = self.get_resource('/', soft=True)
        cls = root.context_cls if root else CMSContext
        return ContextManager(cls, self)



class ContextManager(object):

    def __init__(self, cls, database, user=None, username=None, email=None):
        from server import get_server
        self.context = cls()
        self.context.database = database
        self.context.server = get_server()
        # Get user by user
        if email:
            query = AndQuery(
                PhraseQuery('format', 'user'),
                PhraseQuery('email', email),
            )
            search = database.search(query)
            if search:
                user = search.get_resources(size=1).next()
        # Get user by username
        if username:
            user = self.context.root.get_user(username)
        # Log user
        if user:
            self.context.login(user)
        # Set context
        set_context(self.context)


    def __enter__(self):
        return self.context


    def __exit__(self, exc_type, exc_value, traceback):
        if self.context.database.has_changed:
            msg = 'Warning: Some changes have not been commited'
            print(msg)
        set_context(None)



class Database(RWDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, path, size_min, size_max, catalog=None):
        proxy = super(Database, self)
        proxy.__init__(path, size_min, size_max, catalog)


    def init_context(self, user=None, username=None, email=None):
        from ikaaro.context import CMSContext
        root = self.get_resource('/', soft=True)
        cls = root.context_cls if root else CMSContext
        return ContextManager(cls,
            database=self, user=user, username=username, email=email)


    def close(self):
        # Close
        proxy = super(Database, self)
        return proxy.close()


    def _before_commit(self):
        root = self.get_resource('/')
        context = get_context()
        if context.database != self:
            print context.database, self
            raise ValueError('The contextual database is not coherent')

        # Update resources
        for path in deepcopy(self.resources_new2old):
            resource = root.get_resource(path)
            resource.update_resource(context)

        # 1. Update links when resources moved
        # XXX With this code '_on_move_resource' is called for new resources,
        # should this be done?
        old2new = [ (s, t) for s, t in self.resources_old2new.items()
                    if t and s != t ]
        old2new.sort(key=lambda x: x[1])     # Sort by target
        for source, target in old2new:
            target = Path(target)
            resource = root.get_resource(target)
            resource._on_move_resource(source)

        # 2. Find out resources to re-index because they depend on another
        # resource that changed
        to_reindex = set()
        aux = set()
        aux2 = set(self.resources_old2new.keys())
        while len(aux) != len(aux2):
            aux = set(aux2)
            # XXX we regroup items by 200 because Xapian is slow
            # when there's too much items in OrQuery
            l_aux = list(aux)
            for sub_aux in [l_aux[n:n+200] for n in range(0, len(l_aux), 200)]:
                query = [ PhraseQuery('onchange_reindex', x) for x in sub_aux ]
                query = OrQuery(*query)
                search = self.search(query)
                for brain in search.get_documents():
                    path = brain.abspath
                    aux2.add(path)
                    to_reindex.add(path)

        # 3. Documents to unindex (the update_links methods calls
        # 'change_resource' which may modify the resources_old2new dictionary)
        docs_to_unindex = self.resources_old2new.keys()
        self.resources_old2new.clear()

        # 4. Update mtime/last_author
        user = context.user
        userid = user.name if user else None
        for path in self.resources_new2old:
            if context.set_mtime:
                resource = root.get_resource(path)
                resource.metadata.set_property('mtime', context.timestamp)
                resource.metadata.set_property('last_author', userid)
        # Remove from to_reindex if resource has been deleted
        to_reindex = to_reindex - set(docs_to_unindex)
        # 5. Index
        docs_to_index = self.resources_new2old.keys()
        docs_to_index = set(docs_to_index) | to_reindex
        docs_to_unindex = list(set(docs_to_unindex) - docs_to_index)
        docs_to_index = list(docs_to_index)
        aux = []
        for path in docs_to_index:
            resource = root.get_resource(path, soft=True)
            if resource:
                values = resource.get_catalog_values()
                aux.append((resource, values))
        docs_to_index = aux
        self.resources_new2old.clear()

        # 6. Find out commit author & message
        if user:
            user_email = user.get_value('email')
            git_author = (userid, user_email or 'nobody')
        else:
            git_author = ('nobody', 'nobody')

        git_msg = getattr(context, 'git_message', None)
        if not git_msg:
            if context.method and context.uri:
                git_msg = "%s %s" % (context.method, context.uri)

                action = getattr(context, 'form_action', None)
                if action:
                    git_msg += " action: %s" % action
        else:
            git_msg = git_msg.encode('utf-8')

        # Ok
        git_date = context.fix_tzinfo(context.timestamp)
        return git_author, git_date, git_msg, docs_to_index, docs_to_unindex


    def get_dynamic_classes(self):
        search = self.search(base_classes='-model')
        for brain in search.get_documents():
            class_id = brain.abspath
            yield self.get_resource_class(class_id)



def get_database(path, size_min, size_max, read_only=False):
    if read_only is True:
        return RODatabase(path, size_min, size_max)
    return Database(path, size_min, size_max)
