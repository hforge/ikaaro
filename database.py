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
from itools.database import ROGitDatabase, GitDatabase, make_git_database
from itools.uri import Path
from itools.web import get_context



class Database(GitDatabase):
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

        # 2. Documents to unindex (the update_links methods calls
        # 'change_resource' which may modify the resources_old2new dictionary)
        docs_to_unindex = self.resources_old2new.keys()
        self.resources_old2new.clear()

        # 3. Index
        git_date = context.timestamp
        user = context.user
        userid = user.name if user else None
        docs_to_index = []
        for path in self.resources_new2old:
            resource = root.get_resource(path)
            if context.set_mtime:
                resource.metadata.set_property('mtime', git_date)
                resource.metadata.set_property('last_author', userid)
            values = resource.get_catalog_values()
            docs_to_index.append((resource, values))
        self.resources_new2old.clear()

        # 4. Find out commit author & message
        git_author = (
            (userid, user.get_property('email')) if user else ('nobody', ''))

        git_msg = getattr(context, 'git_message', None)
        if not git_msg:
            git_msg = "%s %s" % (context.method, context.uri)

            action = getattr(context, 'form_action', None)
            if action:
                git_msg += " action: %s" % action
        else:
            git_msg = git_msg.encode('utf-8')

        # Ok
        return git_author, git_date, git_msg, docs_to_index, docs_to_unindex



def make_database(path):
    size_min, size_max = 4800, 5200
    make_git_database(path, size_min, size_max)
    return Database(path, size_min, size_max)


def get_database(path, size_min, size_max, read_only=False):
    if read_only is True:
        return ROGitDatabase(path, size_min, size_max)

    return Database(path, size_min, size_max)
