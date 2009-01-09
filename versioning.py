# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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
from operator import itemgetter
from os import devnull
from subprocess import call, Popen, PIPE

# Import from itools
from itools.datatypes import DateTime, String
from itools.gettext import MSG
from itools import git
from itools.i18n import format_datetime
from itools.uri import get_absolute_reference
from itools import vfs
from itools.web import get_context, STLView
from itools.xapian import KeywordField, BoolField

# Import from ikaaro
from file import File
from metadata import Record


class GitArchive(object):

    def __init__(self, uri, read_only=False):
        uri = get_absolute_reference(uri)
        if uri.scheme != 'file':
            raise IOError, "unexpected '%s' scheme" % uri.scheme

        self.path = str(uri.path)

        # Read Only
        if read_only is True:
            raise NotImplementedError, 'read-only mode not yet implemented'

        # We only track new & changed files, since files removed are
        # automatically handled by 'git commit -a'.
        self.new_files = []


    def save_changes(self):
        # Add
        new_files = [ x for x in self.new_files if vfs.exists(x) ]
        if new_files:
            command = ['git', 'add'] + new_files
            call(command, cwd=self.path)
        if self.new_files:
            self.new_files = []

        # Commit message
        message = 'none'
        context = get_context()
        if context is not None:
            user = context.user
            if user is not None:
                message = user.name
        # Commit
        command = ['git', 'commit', '-a', '-m', message]
        with open(devnull) as null:
            call(command, cwd=self.path, stdout=null)


    def abort_changes(self):
        self.new_files = []
        command = ['git', 'reset', '--']
        call(command, cwd=self.path)


    def add_resource(self, resource):
        for handler in resource.get_handlers():
            path = str(handler.uri.path)
            self.new_files.append(path)



def make_git_archive(path):
    command = ['git', 'init']
    with open(devnull) as null:
        call(command, cwd=path, stdout=null)

    return GitArchive(path)


###########################################################################
# Views
###########################################################################
class HistoryView(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'History')
    icon = 'history.png'
    template = '/ui/file/history.xml'


    def get_namespace(self, resource, context):
        return {
            'revisions': resource.get_revisions(context),
        }



###########################################################################
# Model
###########################################################################
class History(Record):

    schema = {
        'date': DateTime,
        'user': String,
        'size': String}


class VersioningAware(File):

    def get_revisions(self, context=None):
        if context is None:
            context = get_context()

        accept = context.accept_language

        # Get the list of revisions
        command = ['git', 'rev-list', 'HEAD', '--']
        for handler in self.get_handlers():
            path = str(handler.uri.path)
            command.append(path)
        cwd = context.server.archive.path
        pipe = Popen(command, cwd=cwd, stdout=PIPE).stdout

        # Get the metadata
        revisions = []
        for line in pipe.readlines():
            line = line.strip()
            metadata = git.get_metadata(line, cwd=cwd)
            date = metadata['committer'][1]
            username = metadata['message'].strip()
            revisions.append({
                'username': username,
                'date': format_datetime(date, accept=accept)})

        return revisions


    def get_owner(self):
        revisions = self.get_revisions()
        if not revisions:
            return None
        return revisions[-1]['username']


    def get_last_author(self):
        revisions = self.get_revisions()
        if not revisions:
            return None
        return revisions[0]['username']


    def get_mtime(self):
        revisions = self.get_revisions()
        if not revisions:
            return File.get_mtime(self)
        return revisions[0]['date']


    ########################################################################
    # Index & Search
    ########################################################################
    def get_catalog_fields(self):
        return File.get_catalog_fields(self) + [
            # Versioning Aware
            BoolField('is_version_aware'),
            KeywordField('last_author', is_indexed=False, is_stored=True)]


    def get_catalog_values(self):
        document = File.get_catalog_values(self)

        document['is_version_aware'] = True
        # Last Author (used in the Last Changes view)
        last_author = self.get_last_author()
        if last_author is not None:
            users = self.get_resource('/users')
            try:
                user = users.get_resource(last_author)
            except LookupError:
                document['last_author'] = None
            else:
                document['last_author'] = user.get_title()

        return document


    ########################################################################
    # User Interface
    ########################################################################
    history = HistoryView()
