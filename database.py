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
from subprocess import call, PIPE

# Import from itools
from itools.core import get_pipe
from itools.handlers import ROGitDatabase, GitDatabase, make_git_database
from itools.http import get_context
from itools.xapian import Catalog, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields



class ReadOnlyDatabase(ROGitDatabase):

    def __init__(self, target, cache_size):
        self.path = '%s/database' % target

        # Database/Catalog
        ROGitDatabase.__init__(self, self.path, cache_size)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields(),
                               read_only=True)



class Database(GitDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, target, cache_size):
        # Database/Catalog
        path = '%s/database' % target
        GitDatabase.__init__(self, path, cache_size)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields())


    def _save_changes(self, data):
        git_author, git_message, docs_to_index, docs_to_unindex = data

        # (1) Save filesystem changes
        GitDatabase._save_changes(self, (git_author, git_message))

        # (2) Catalog
        catalog = self.catalog
        for path in docs_to_unindex:
            catalog.unindex_document(path)
        for resource, values in docs_to_index:
            values = resource.get_catalog_values(values)
            catalog.index_document(values)
        catalog.save_changes()


    def _abort_changes(self):
        GitDatabase._abort_changes(self)
        self.catalog.abort_changes()



def make_database(target):
    size = 5000
    # GitDatabase
    path = '%s/database' % target
    make_git_database(path, size)
    # The catalog
    make_catalog('%s/catalog' % target, get_register_fields())
    # Ok
    return Database(target, size)


def get_database(path, cache_size, read_only=False):
    if read_only is True:
        return ReadOnlyDatabase(path, cache_size)

    return Database(path, cache_size)


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
