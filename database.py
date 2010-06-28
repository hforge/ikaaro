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
from itools.core import get_pipe
from itools.database import ROGitDatabase, GitDatabase, make_git_database
from itools.uri import Path
from itools.web import get_context



class Database(GitDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, path, size_min, size_max):
        super(Database, self).__init__(path, size_min, size_max)

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
        self.resources_old2new = {}
        self.resources_new2old = {}


    #######################################################################
    # Events API
    #######################################################################
    def remove_resource(self, resource):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        for x in resource.traverse_resources():
            path = str(x.get_canonical_path())
            old2new[path] = None
            new2old.pop(path, None)


    def add_resource(self, resource):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        # Catalog
        for x in resource.traverse_resources():
            path = str(x.get_canonical_path())
            new2old[path] = None


    def change_resource(self, resource):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        path = str(resource.get_canonical_path())
        if path in old2new and not old2new[path]:
            raise ValueError, 'cannot change a resource that has been removed'

        if path not in new2old:
            old2new[path] = path
            new2old[path] = path


    def move_resource(self, source, new_path):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        old_path = source.get_canonical_path()
        for x in source.traverse_resources():
            source_path = x.get_canonical_path()
            target_path = new_path.resolve2(old_path.get_pathto(source_path))

            source_path = str(source_path)
            target_path = str(target_path)
            if source_path in old2new and not old2new[source_path]:
                err = 'cannot move a resource that has been removed'
                raise ValueError, err

            source_path = new2old.pop(source_path, source_path)
            if source_path:
                old2new[source_path] = target_path
            new2old[target_path] = source_path


    #######################################################################
    # Transactions API
    #######################################################################
    def _before_commit(self):
        context = get_context()
        root = context.root

        # 1. Update links when resources moved
        for source, target in self.resources_old2new.items():
            if target and source != target:
                target = Path(target)
                resource = root.get_resource(target)
                resource._on_move_resource(source)

        # 2. Documents to unindex (the update_links methods calls
        # server.change_resource which may modify the resources_old2new
        # dictionary)
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
        git_msg = 'no comment'
        git_author = (
            '%s <%s>' % (userid, user.get_property('email'))
            if user else 'nobody <>')
        git_msg = getattr(context, 'git_message', None)
        git_msg = (
            git_msg.encode('utf-8')
            if git_msg else "%s %s" % (context.method, context.uri))

        # Ok
        return git_author, git_date, git_msg, docs_to_index, docs_to_unindex


    def _save_changes(self, data):
        git_author, git_date, git_msg, docs_to_index, docs_to_unindex = data

        # 1. Save filesystem changes
        GitDatabase._save_changes(self, (git_author, git_date, git_msg))

        # 2. Catalog
        catalog = self.catalog
        for path in docs_to_unindex:
            catalog.unindex_document(path)
        for resource, values in docs_to_index:
            catalog.index_document(values)
        catalog.save_changes()


    def _abort_changes(self):
        GitDatabase._abort_changes(self)

        # Catalog
        self.catalog.abort_changes()

        # Clear events
        self.resources_old2new.clear()
        self.resources_new2old.clear()



def make_database(path):
    size_min, size_max = 4800, 5200
    make_git_database(path, size_min, size_max)
    return Database(path, size_min, size_max)


def get_database(path, size_min, size_max, read_only=False):
    if read_only is True:
        return ROGitDatabase(path, size_min, size_max)

    return Database(path, size_min, size_max)


def check_database(target):
    """This function checks whether the database is in a consisitent state,
    this is to say whether a transaction was not brutally aborted and left
    the working directory with changes not committed.

    This is meant to be used by scripts, like 'icms-start.py'
    """
    cwd = '%s/database' % target

    # Check modifications to the working tree not yet in the index.
    command = ['git', 'ls-files', '-m', '-d', '-o']
    data1 = get_pipe(command, cwd=cwd)

    # Check changes in the index not yet committed.
    command = ['git', 'diff-index', '--cached', '--name-only', 'HEAD']
    data2 = get_pipe(command, cwd=cwd)

    # Everything looks fine
    if len(data1) == 0 and len(data2) == 0:
        return True

    # Something went wrong
    print 'The database is not in a consistent state.  Fix it manually with'
    print 'the help of Git:'
    print
    print '  $ cd %s/database' % target
    print '  $ git clean -fxd'
    print '  $ git checkout -f'
    print
    return False
