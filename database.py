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
from itools.core import LRUCache
from itools import git
from itools.handlers import RODatabase, SolidDatabase
from itools import vfs
from itools.vfs import cwd
from itools.web import get_context
from itools.xapian import Catalog, make_catalog

# Import from ikaaro
from folder import Folder
from registry import get_register_fields


class GitCommon(object):

    def __init__(self, target):
        self.path = '%s/database' % target
        self.git_cache = LRUCache(50)


    def get_revision(self, revision_key):
        cache = self.git_cache
        if revision_key in cache:
            return cache[revision_key]

        cwd = self.path
        metadata = git.get_metadata(revision_key, cwd=cwd)
        date = metadata['committer'][1]
        username = metadata['author'][0].split()[0]
        if username == 'nobody':
            username = None
        revision = {
            'username': username,
            'date': date,
            'message': metadata['message'],
            'revision': revision_key}
        cache[revision_key] = revision
        return revision



class ReadOnlyDatabase(GitCommon, RODatabase):

    def __init__(self, target):
        GitCommon.__init__(self, target)

        # Database/Catalog
        RODatabase.__init__(self)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields(),
                               read_only=True)



class Database(GitCommon, SolidDatabase):
    """Adds a Git archive to the itools database.
    """

    def __init__(self, target):
        GitCommon.__init__(self, target)

        # Database/Catalog
        SolidDatabase.__init__(self, '%s/database.commit' % target)
        self.catalog = Catalog('%s/catalog' % target, get_register_fields())

        # Events
        self.resources_added = {}
        self.resources_changed = {}
        self.resources_removed = set()


    #######################################################################
    # Events API
    #######################################################################
    def remove_resource(self, resource):
        resources_removed = self.resources_removed
        resources_added = self.resources_added

        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                if path in resources_added:
                    del resources_added[path]
                resources_removed.add(path)
        else:
            path = str(resource.get_canonical_path())
            if path in resources_added:
                del resources_added[path]
            resources_removed.add(path)


    def add_resource(self, resource):
        resources_added = self.resources_added

        # Catalog
        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                resources_added[path] = x
        else:
            path = str(resource.get_canonical_path())
            resources_added[path] = resource


    def change_resource(self, resource):
        path = str(resource.get_canonical_path())
        self.resources_changed[path] = resource


    #######################################################################
    # Transactions API
    #######################################################################
    def _before_commit(self):
        catalog = self.catalog
        git_files = []

        # Removed
        for path in self.resources_removed:
            catalog.unindex_document(path)
        self.resources_removed.clear()

        # Added
        resources_added = self.resources_added
        for path in resources_added:
            resource = resources_added[path]
            git_files.extend(resource.get_files_to_archive())

        # Changed
        for path in self.resources_changed:
            catalog.unindex_document(path)

        # Find out commit author & message
        git_author = 'nobody <>'
        git_message = 'no comment'
        context = get_context()
        if context is not None:
            # Author
            user = context.user
            if user is not None:
                email = user.get_property('email')
                git_author = '%s <%s>' % (user.name, email)
            # Message
            try:
                git_message = getattr(context, 'git_message')
            except AttributeError:
                pass
            else:
                git_message = git_message.encode('utf-8')

        # Ok
        return git_files, git_author, git_message


    def _save_changes(self, data):
        # (1) Save filesystem changes
        SolidDatabase._save_changes(self, data)

        # Unpack data
        git_files, git_author, git_message = data

        # (2) Git
        git_files = [ x for x in git_files if vfs.exists(x) ]
        if git_files:
            command = ['git', 'add'] + git_files
            call(command, cwd=self.path)

        # TODO Don't commit if there is nothing to commit (e.g. when login)
        command = ['git', 'commit', '-aq', '--author=%s' % git_author,
                   '-m', git_message]
        call(command, cwd=self.path, stdout=PIPE)

        # (3) Catalog
        catalog = self.catalog
        # Added
        for path, resource in self.resources_added.iteritems():
            catalog.index_document(resource)
        self.resources_added.clear()
        # Changed
        for path, resource in self.resources_changed.iteritems():
            catalog.index_document(resource)
        self.resources_changed.clear()
        # Save
        catalog.save_changes()


    def _abort_changes(self):
        SolidDatabase._abort_changes(self)

        # Git
        command = ['git', 'reset', '--']
        call(command, cwd=self.path)

        # Catalog
        self.catalog.abort_changes()

        # Clear events
        self.resources_removed.clear()
        self.resources_added.clear()
        self.resources_changed.clear()



def make_database(target):
    # Init git
    path = '%s/database' % target
    command = ['git', 'init']
    call(command, cwd=path)

    # The catalog
    make_catalog('%s/catalog' % target, get_register_fields())

    # Ok
    return Database(target)


def get_database(path, read_only=False):
    if read_only is True:
        return ReadOnlyDatabase(path)

    return Database(path)
