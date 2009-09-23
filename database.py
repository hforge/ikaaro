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

# Import from itools
from itools.core import get_pipe, send_subprocess
from itools.handlers import ROGitDatabase, GitDatabase, make_git_database
from itools.http import get_context
from itools.uri import Path
from itools.xapian import Catalog, SearchResults, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields, get_resource_class



class CMSSearchResults(SearchResults):

    def get_documents(self, sort_by=None, reverse=False, start=0, size=0):
        context = get_context()
        host = context.host
        if host:
            host = len(host)+1

        docs = SearchResults.get_documents(self, sort_by, reverse, start, size)
        for brain in docs:
            key = brain.abspath
            if host:
                key = key[host:] or '/'
            resource = context.cache.get(key)

            if resource:
                # Cache hit
                yield resource
            else:
                # Cache miss
                cls = get_resource_class(brain.format)
                resource = cls(brain=brain)
                resource.context = context
                resource.path = Path(key)
                context.cache[key] = resource
                yield resource



class ReadOnlyDatabase(ROGitDatabase):

    def __init__(self, target, size_min, size_max):
        self.path = '%s/database' % target

        # Database/Catalog
        ROGitDatabase.__init__(self, self.path, size_min, size_max)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields(),
                               read_only=True)

        # Git cache (lazy load)
        self.git_cache = None


    def get_revisions(self, files, n=None):
        cmd = ['git', 'rev-list', '--pretty=format:%an%n%at%n%s']
        if n is not None:
            cmd = cmd + ['-n', str(n)]
        cmd = cmd + ['HEAD', '--'] + files
        data = send_subprocess(cmd)

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
        cmd = ['git', 'log', '--pretty=format:%H%n%an%n%at%n%s', '--raw']
        data = send_subprocess(cmd)
        lines = data.splitlines()
        while lines:
            date = int(lines[2])
            commit = {
                'revision': lines[0],                 # commit
                'username': lines[1],                 # author name
                'date': datetime.fromtimestamp(date), # author date
                'message': lines[3],                  # subject
                }
            # Modified files
            lines = lines[4:]
            while lines and lines[0]:
                file = lines[0].rsplit('\t', 1)[1]
                self.git_cache.setdefault(file, commit)
                lines = lines[1:]
            lines = lines[1:]


    def get_last_revision(self, files):
        if self.git_cache is None:
            self.load_git_cache()

        n = len(self.path)
        last_commit = None

        for file in files:
            file = file[n:]
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
        # Database/Catalog
        path = '%s/database' % target
        GitDatabase.__init__(self, path, size_min, size_max)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields())
        self.catalog.search_results = CMSSearchResults


    def get_last_revision(self, files):
        # The git cache only works on read-only mode
        revisions = self.get_revisions(files, 1)
        return revisions[0] if revisions else None


    def _save_changes(self, data):
        git_author, git_message, docs_to_index, docs_to_unindex = data

        # (1) Save filesystem changes
        GitDatabase._save_changes(self, (git_author, git_message))

        # (2) Catalog
        catalog = self.catalog
        for path in docs_to_unindex:
            catalog.unindex_document(path)
        for resource in docs_to_index:
            catalog.index_document(resource)
        catalog.save_changes()


    def _abort_changes(self):
        GitDatabase._abort_changes(self)
        self.catalog.abort_changes()



def make_database(target):
    make_git_database('%s/database' % target, 4800, 5200)
    make_catalog('%s/catalog' % target, get_register_fields())


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
    command = ['git', 'diff-index', 'HEAD', '--name-only']
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
