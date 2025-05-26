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

import asyncio
import copy

# Import from itools
from itools.database import RWDatabase, RODatabase as BaseRODatabase
from itools.database import OrQuery, PhraseQuery, AndQuery
from itools.uri import Path
from itools.web import get_context, set_context


NB_READS = 1
DBSEM_RO = asyncio.BoundedSemaphore(NB_READS)
DBSEM_RW = asyncio.BoundedSemaphore(1)


class RODatabase(BaseRODatabase):

    def init_context(
            self,
            user=None,
            username=None,
            email=None,
            commit_at_exit=True,
            read_only=True
    ):
        from ikaaro.context import CMSContext
        root = self.get_resource('/', soft=True)
        cls = root.context_cls if root else CMSContext
        return ContextManager(cls, self, read_only=read_only)



class ContextManager:

    def __init__(
            self,
            cls,
            database,
            user=None,
            username=None,
            email=None,
            commit_at_exit=True,
            read_only=False
    ):
        # Check if context is not already locked
        if get_context() is not None:
            raise ValueError('Cannot acquire context. Already locked.')

        self.user = user
        self.username = username
        self.email = email
        self.commit_at_exit = commit_at_exit
        self.read_only = read_only

        # Create context
        self.context = cls()
        self.context.database = database


    async def __aenter__(self):
        from .server import get_server

        # Acquire lock on database
        if self.read_only:
            async with DBSEM_RW:  # Wait for rw semaphore to be available
                pass

            await DBSEM_RO.acquire()
        else:
            await DBSEM_RW.acquire()
            for _ in range(NB_READS):
                await DBSEM_RO.acquire()

        # Set context
        self.context.server = get_server()
        set_context(self.context)

        # Get user
        if self.user:
            user = self.user
        elif self.username:
            user = self.context.root.get_user(self.username)
        elif self.email:
            query = AndQuery(
                PhraseQuery('format', 'user'),
                PhraseQuery('email', self.email),
            )
            search = self.context.database.search(query)
            if search:
                user = next(search.get_resources(size=1))
        else:
            user = None

        # Log in
        if user:
            self.context.login(user)

        return self.context


    async def __aexit__(self, exc_type, exc_value, traceback):
        try:
            if self.commit_at_exit:
                self.context.database.save_changes()
            else:
                if self.context.database.has_changed:
                    print('Warning: Some changes have not been commited')
        finally:
            set_context(None)
            if self.read_only:
                DBSEM_RO.release()
            else:
                for _ in range(NB_READS):
                    DBSEM_RO.release()
                DBSEM_RW.release()



class Database(RWDatabase):
    """Adds a Git archive to the itools database.
    """

    def init_context(
            self,
            user=None,
            username=None,
            email=None,
            commit_at_exit=True,
            read_only=False
    ):
        from ikaaro.context import CMSContext
        root = self.get_resource('/', soft=True)
        cls = root.context_cls if root else CMSContext
        return ContextManager(
            cls,
            database=self, user=user,
            username=username, email=email,
            commit_at_exit=commit_at_exit,
            read_only=read_only
        )


    def close(self):
        # Close
        proxy = super()
        return proxy.close()


    def _before_commit(self):
        root = self.get_resource('/')
        context = get_context()
        if context.database != self:
            raise ValueError('The contextual database is not coherent')

        # Update resources
        for path in copy.deepcopy(self.resources_new2old):
            resource = root.get_resource(path)
            resource.update_resource(context)

        # 1. Update links when resources moved
        # XXX With this code '_on_move_resource' is called for new resources,
        # should this be done?
        old2new = [ (s, t) for s, t in self.resources_old2new.items()
                    if t and s != t ]
        old2new = sorted(old2new, key=lambda x: x[1]) # Sort by target
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
        docs_to_unindex = list(self.resources_old2new.keys())
        self.resources_old2new.clear()

        # 4. Update mtime/last_author
        user = context.user
        userid = user.name if user else None
        for path in self.resources_new2old:
            if context.set_mtime:
                resource = root.get_resource(path)
                handler = resource.metadata
                if handler.dirty:
                    # Save mtime, only if there's really changes
                    # (if we reindex resource, no need to update mtime)
                    handler.set_property('mtime', context.timestamp)
                    handler.set_property('last_author', userid)
        # Remove from to_reindex if resource has been deleted
        to_reindex = to_reindex - set(docs_to_unindex)
        # 5. Index
        docs_to_index = list(self.resources_new2old.keys())
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
                git_msg = f"{context.method} {context.uri}"

                action = getattr(context, 'form_action', None)
                if action:
                    git_msg += f" action: {action}"
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



def get_database(path, size_min, size_max, read_only=False, backend='git'):
    if read_only is True:
        return RODatabase(path, size_min, size_max, backend=backend)
    return Database(path, size_min, size_max, backend=backend)
