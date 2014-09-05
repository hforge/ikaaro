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
from itools.database import RODatabase, RWDatabase, make_git_database
from itools.database import OrQuery, PhraseQuery
from itools.uri import Path
from itools.web import get_context


class Database(RWDatabase):
    """Adds a Git archive to the itools database.
    """

    def _before_commit(self):
        context = get_context()
        root = context.root

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
            query = [ PhraseQuery('onchange_reindex', x) for x in aux ]
            query = OrQuery(*query)
            search = self.search(query)
            for brain in search.get_documents():
                path = brain.abspath
                aux2.add(path)
                to_reindex.add(path)

        # 3. Documents to unindex (the update_links methods calls
        # 'change_resource' which may modify the resources_old2new dictionary)
        docs_to_unindex = self.resources_old2new.keys()
        docs_to_unindex = list(set(docs_to_unindex) | to_reindex)
        self.resources_old2new.clear()

        # 4. Update mtime/last_author
        user = context.user
        userid = user.name if user else None
        if context.set_mtime:
            for path in self.resources_new2old:
                resource = root.get_resource(path)
                resource.metadata.set_property('mtime', context.timestamp)
                resource.metadata.set_property('last_author', userid)

        # 5. Index
        docs_to_index = self.resources_new2old.keys()
        docs_to_index = list(set(docs_to_index) | to_reindex)
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
            git_author = (userid, user.get_value('email'))
        else:
            git_author = ('nobody', 'nobody')

        git_msg = getattr(context, 'git_message', None)
        if not git_msg:
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



def make_database(path):
    size_min, size_max = 19500, 20500
    make_git_database(path, size_min, size_max)
    return Database(path, size_min, size_max)


def get_database(path, size_min, size_max, read_only=False):
    if read_only is True:
        return RODatabase(path, size_min, size_max)

    return Database(path, size_min, size_max)
