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

# Import from the Standard Library
from datetime import datetime

# Import from xapian
from xapian import DatabaseError, DatabaseOpeningError

# Import from itools
from itools.core import get_pipe, lazy, send_subprocess
from itools.handlers import ROGitDatabase, GitDatabase, make_git_database
from itools.uri import Path
from itools.web import get_context
from itools.xapian import Catalog, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields
from table import Table


class ReadOnlyDatabase(ROGitDatabase):

    def __init__(self, target, size_min, size_max):
        self.target = target
        # Call parent class
        path = '%s/database' % target
        ROGitDatabase.__init__(self, path, size_min, size_max)

        # Git cache (lazy load)
        self.git_cache = None


    @lazy
    def catalog(self):
        path = '%s/catalog' % self.target
        fields = get_register_fields()
        try:
            return Catalog(path, fields, read_only=True)
        except (DatabaseError, DatabaseOpeningError):
            return None


    def get_revisions(self, files, n=None, author=None, grep=None):
        cmd = ['git', 'rev-list', '--pretty=format:%an%n%at%n%s']
        if n is not None:
            cmd = cmd + ['-n', str(n)]
        if author is not None:
            cmd += ['--author=%s' % author]
        if grep is not None:
            cmd += ['--grep=%s' % grep]
        cmd = cmd + ['HEAD', '--'] + files
        data = send_subprocess(cmd, path=self.path)

        # Parse output
        revisions = []
        lines = data.splitlines()
        for idx in range(len(lines) / 4):
            base = idx * 4
            ts = int(lines[base+2])
            revisions.append(
                {'revision': lines[base].split()[1], # commit
                 'username': lines[base+1],          # author name
                 'date': datetime.fromtimestamp(ts), # author date
                 'message': lines[base+3],           # subject
                })
        # Ok
        return revisions


    def load_git_cache(self):
        self.git_cache = {}
        cmd = ['git', 'log', '--pretty=format:%H%n%an%n%at%n%s', '--raw',
               '--name-only']
        data = send_subprocess(cmd, path=self.path)
        lines = data.splitlines()
        i = 0
        while i < len(lines):
            date = int(lines[i + 2])
            commit = {
                'revision': lines[i],                 # commit
                'username': lines[i + 1],             # author name
                'date': datetime.fromtimestamp(date), # author date
                'message': lines[i + 3],              # subject
                }
            # Modified files
            i += 4
            while i < len(lines) and lines[i]:
                self.git_cache.setdefault(lines[i], commit)
                i += 1
            # Next entry is separated by an empty line
            i += 1


    def get_last_revision(self, files):
        if self.git_cache is None:
            self.load_git_cache()

        last_commit = None

        for file in files:
            commit = self.git_cache.get(file)
            if not commit:
                continue
            if not last_commit or commit['date'] > last_commit['date']:
                last_commit = commit

        return last_commit



class Database(ReadOnlyDatabase, GitDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, target, size_min, size_max):
        self.target = target
        # Call parent class
        path = '%s/database' % target
        GitDatabase.__init__(self, path, size_min, size_max)

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


    @lazy
    def catalog(self):
        path = '%s/catalog' % self.target
        return Catalog(path, get_register_fields())


    #######################################################################
    # Git API
    #######################################################################
    def get_last_revision(self, files):
        # The git cache only works on read-only mode
        revisions = self.get_revisions(files, 1)
        return revisions[0] if revisions else None


    #######################################################################
    # Events API
    #######################################################################
    def remove_resource(self, resource):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                old2new[path] = None
                new2old.pop(path, None)
        else:
            path = str(resource.get_canonical_path())
            old2new[path] = None
            new2old.pop(path, None)


    def add_resource(self, resource):
        old2new = self.resources_old2new
        new2old = self.resources_new2old

        # Catalog
        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                new2old[path] = None
                # Reindex each record of tables (cf. Paste table)
                item_resource = resource.get_resource(path, soft=True)
                if item_resource and isinstance(item_resource, Table):
                    item_resource.reindex_records()
        else:
            path = str(resource.get_canonical_path())
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

        def f(source_path, target_path):
            source_path = str(source_path)
            target_path = str(target_path)

            if source_path in old2new and not old2new[source_path]:
                raise ValueError, 'cannot move a resource that has been removed'

            source_path = new2old.pop(source_path, source_path)
            if source_path:
                old2new[source_path] = target_path
            new2old[target_path] = source_path


        old_path = source.get_canonical_path()
        if isinstance(source, Folder):
            for x in source.traverse_resources():
                x_old_path = x.get_canonical_path()
                x_new_path = new_path.resolve2(old_path.get_pathto(x_old_path))
                f(x_old_path, x_new_path)
        else:
            f(old_path, new_path)


    #######################################################################
    # Transactions API
    #######################################################################
    def _before_commit(self):
        context = get_context()
        root = context.root
        catalog = self.catalog
        docs_to_index = []

        # Update links when resources moved
        for source, target in self.resources_old2new.items():
            if target and source != target:
                target = Path(target)
                resource = root.get_resource(target)
                resource._on_move_resource(source)

        # Get documents to unindex
        # update_links methods call server.change_resource
        # which update resources_old2new dictionary
        docs_to_unindex = self.resources_old2new.keys()

        # Clear resources_old2new
        self.resources_old2new.clear()

        # Index
        for path in self.resources_new2old:
            resource = root.get_resource(path)
            values = resource._get_catalog_values()
            docs_to_index.append((resource, values))
        self.resources_new2old.clear()

        # Find out commit author & message
        user = context.user
        userid = user.name if user else None
        if user:
            git_author = (userid, user.get_property('email'))
        else:
            git_author = ('nobody', 'nobody')

        git_message = 'no comment'
        if context is not None:
            # Message
            try:
                git_message = getattr(context, 'git_message')
            except AttributeError:
                git_message = "%s %s" % (context.method, context.uri)
            else:
                git_message = git_message.encode('utf-8')

        # Ok
        git_date = context.fix_tzinfo(context.timestamp)
        return git_author, git_date, git_message, docs_to_index, docs_to_unindex


    def _save_changes(self, data):
        git_author, git_date, git_message, docs_to_index, docs_to_unindex = data

        # (1) Save filesystem changes
        GitDatabase._save_changes(self, data)

        # Catalog
        # (2) UnIndex
        catalog = self.catalog
        for path in docs_to_unindex:
            catalog.unindex_document(path)

        # (3) Index
        mtime = datetime.now() # XXX This is an approximation, not exactly the
                               # same as returned by git
        user = get_context().user
        author = user.get_title() if user else None
        for resource, values in docs_to_index:
            values['mtime'] = mtime
            values['last_author'] = author
            catalog.index_document(values)
        catalog.save_changes()


    def _abort_changes(self):
        GitDatabase._abort_changes(self)

        # Catalog
        self.catalog.abort_changes()

        # Clear events
        self.resources_old2new.clear()
        self.resources_new2old.clear()



def make_database(target):
    size_min, size_max = 4800, 5200
    # GitDatabase
    make_git_database(target, size_min, size_max)
    # The catalog
    make_catalog('%s/catalog' % target, get_register_fields())
    # Ok
    return Database(target, size_min, size_max)


def get_database(path, size_min, size_max, read_only=False):
    if read_only is True:
        return ReadOnlyDatabase(path, size_min, size_max)

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
