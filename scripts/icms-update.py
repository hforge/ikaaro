#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
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
from cProfile import runctx
from datetime import datetime
from optparse import OptionParser
from subprocess import Popen, PIPE
from sys import exit, stdout
from time import time
from traceback import print_exc

# Import from itools
import itools
from itools.core import fixed_offset, start_subprocess, send_subprocess
from itools.csv import Property
from itools.database import check_database
from itools.fs import lfs
from itools.handlers import ro_database
from itools.web import get_context

# Import from ikaaro
from ikaaro.config import get_config
from ikaaro.metadata import Metadata
from ikaaro.obsolete.metadata import OldMetadata
from ikaaro.resource_ import DBResource
from ikaaro.server import Server, ask_confirmation, get_fake_context, get_pid
from ikaaro.server import load_modules


def abort():
    print '*'
    print '* Upgrade process not finished!'
    print '*'
    exit(0)



def find_versions_to_update(root, force=False):
    print 'STAGE 1: Find next version to upgrade (may take a while).'
    version = None
    paths = None

    # Find out the versions to upgrade
    for resource in root.traverse_resources():
        # Skip non-database resources
        if not isinstance(resource, DBResource):
            continue

        # Skip up-to-date resources
        obj_version = resource.metadata.version
        cls_version = resource.class_version
        if obj_version == cls_version:
            continue

        # Check for code that is older than the instance
        if obj_version > cls_version:
            print
            print '* %s resource=%s class=%s' % (resource.get_abspath(),
                resource.metadata.format, resource.__class__)
            print '* the resource is newer than its class: %s > %s' % (
                obj_version, cls_version)
            if force is False:
                exit()

        next_versions = resource.get_next_versions()
        if not next_versions:
            continue

        stdout.write('.')
        stdout.flush()
        next_version = next_versions[0]
        if version is None or next_version < version:
            version = next_version
            paths = [resource.get_abspath()]
        elif next_version == version:
            paths.append(resource.get_abspath())

    return version, paths



def update_versions(target, database, version, paths, root, force=False):
    """Update the database to the given versions.
    """
    # Open the update log
    log = open('%s/log/update' % target, 'w')

    # Update
    bad = 0
    resources_old2new = database.resources_old2new
    for path in paths:
        abspath = resources_old2new.get(path, path)
        if abspath is None:
            # resource deleted
            continue

        # Skip up-to-date resources
        resource = root.get_resource(abspath)
        obj_version = resource.metadata.version
        cls_version = resource.class_version
        if obj_version == cls_version:
            continue

        next_versions = resource.get_next_versions()
        if not next_versions:
            continue

        if next_versions[0] != version:
            continue

        # Update
        stdout.write('.')
        stdout.flush()
        try:
            resource.update(version)
        except Exception:
            line = '%s %s\n' % (resource.get_abspath(), resource.__class__)
            if force:
                log.write(line)
                print_exc(file=log)
                log.write('\n')
                bad += 1
            else:
                print line
                raise
    # Commit
    context = get_context()
    context.git_message = u'Upgrade to version %s' % version
    context.set_mtime = False # Do not override the mtime/author
    database.save_changes()
    # Stop if there were errors
    print
    if bad > 0:
        print '*'
        print '* ERROR: %s resources failed to upgrade to version %s' \
              % (bad, version)
        print '* Check the "%s/log/update" file.' % target
        print '*'
        exit(1)



def update(parser, options, target):
    confirm = options.confirm

    # Check the server is not started, or started in read-only mode
    pid = get_pid('%s/pid' % target)
    if pid is not None:
        print 'Cannot proceed, the server is running in read-write mode.'
        return

    # Check for database consistency
    if options.quick is False and check_database(target) is False:
        return 1

    # Start subprocess
    path = '%s/database' % target
    start_subprocess(path)

    # Load the modules
    config = get_config(target)
    load_modules(config)

    #######################################################################
    # STAGE 0: Change format of the metadata
    # XXX Specific to the migration from 0.61 to 0.62
    #######################################################################
    metadata = ro_database.get_handler('%s/.metadata' % path, Metadata)
    try:
        metadata.load_state()
    except SyntaxError:
        ro_database.cache.clear()
        message = 'STAGE 0: Update metadata to the new format (y/N)? '
        if ask_confirmation(message, confirm) is False:
            abort()
        print 'STAGE 0: Updating metadata (may take a while)'
        t0 = time()

        for filename in lfs.traverse(path):
            if not filename.endswith('.metadata'):
                continue
            # Load the old metadata
            old_metadata = ro_database.get_handler(filename, OldMetadata)
            old_metadata.load_state()
            # Make the new metadata
            format = old_metadata.format
            version = old_metadata.version
            new_metadata = Metadata(format=format, version=version)
            # Copy properties
            for name in old_metadata.properties:
                value = old_metadata.properties[name]
                if type(value) is dict:
                    for lang in value:
                        property = Property(value[lang], lang=lang)
                        new_metadata.set_property(name, property)
                elif type(value) is list:
                    property = [ Property(x) for x in value ]
                    new_metadata.set_property(name, property)
                else:
                    property = Property(value)
                    new_metadata.set_property(name, property)
            # Save
            del old_metadata
            lfs.remove(filename)
            new_metadata.save_state_to(filename)
        print '       : %f seconds' % (time() - t0)
        # Commit
        print 'STAGE 0: Committing changes to git (may take a while)'
        t0 = time()
        command = ['git', 'commit', '-a', '--author=nobody <>',
                   '-m', 'Update metadata to new format']
        p = Popen(command, cwd=path, stdout=PIPE)
        p.communicate()
        print '       : %f seconds' % (time() - t0)

    #######################################################################
    # STAGE 0 (follow-up): Set mtime/author
    # XXX Specific to the migration from 0.61 to 0.62
    #######################################################################
    server = Server(target)
    # Build a fake context
    context = get_fake_context()
    server.init_context(context)
    # Local variables
    database = server.database
    root = server.root

    mtime = root.get_property('mtime')
    if mtime is None or options.mtime:
        message = 'STAGE 0: Set mtime and author in the metadata (y/N)? '
        if ask_confirmation(message, confirm) is False:
            abort()

        # Find out set of valid usernames
        usernames = root.get_names('users')
        usernames = set(usernames)

        print 'STAGE 0: Initializing mtime/author'
        # Load cache
        git_cache = {}
        cmd = ['git', 'log', '--pretty=format:%H%n%an%n%at%n%s', '--raw',
               '--name-only']
        data = send_subprocess(cmd)
        lines = data.splitlines()
        utc = fixed_offset(0)
        i = 0
        while i < len(lines):
            date = int(lines[i + 2])
            author = lines[i + 1]
            if author not in usernames:
                author = None
            commit = {
                'revision': lines[i],                      # commit
                'username': author,                        # author name
                'date': datetime.fromtimestamp(date, utc), # author date
                'message': lines[i + 3]}                   # subject

            # Modified files
            i += 4
            while i < len(lines) and lines[i]:
                path = lines[i]
                if path not in git_cache or not git_cache[path]['username']:
                    git_cache[path] = commit
                i += 1
            # Next entry is separated by an empty line
            i += 1

        # Set mtime/author
        for resource in root.traverse_resources():
            if not isinstance(resource, DBResource):
                continue

            files = resource.get_files_to_archive()
            last_commit = None
            for file in files:
                commit = git_cache.get(file)
                if not commit:
                    continue
                if not last_commit or commit['date'] > last_commit['date']:
                    last_commit = commit
            metadata = resource.metadata
            metadata.set_property('mtime', last_commit['date'])
            metadata.set_property('last_author', last_commit['username'])

        # Commit
        context.git_message = u'Upgrade: set mtime/author'
        context.set_mtime = False # Do not override the mtime/author
        database.save_changes()


    #######################################################################
    # STAGE 1: Find out the versions to upgrade
    #######################################################################
    print 'STAGE 1: Find out the versions to upgrade (may take a while).'
    version, paths = find_versions_to_update(root, options.force)
    while version:
        message = 'STAGE 1: Upgrade %d resources to version %s (y/N)? '
        message = message % (len(paths), version)
        if ask_confirmation(message, confirm) is False:
            abort()
        update_versions(target, database, version, paths, root, options.force)
        # Reset the state
        database.cache.clear()
        database.cache[root.metadata.key] = root.metadata
        print 'STAGE 1: Finish upgrading to version %s' % version
        version, paths = find_versions_to_update(root, options.force)

    print 'STAGE 1: Done.'

    # It is Done
    print '*'
    print '* To finish the upgrade process update the catalog:'
    print '*'
    print '*   $ icms-update-catalog.py %s' % target
    print '*'



if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % itools.__version__
    description = ('Updates the TARGET ikaaro instance (if needed). Use'
                   ' this command when upgrading to a new version of itools.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option('-y', '--yes', action='store_true', dest='confirm',
        help="start the update without asking confirmation")
    parser.add_option('--force', action='store_true', default=False,
        help="continue the upgrade process in spite of errors")
    parser.add_option('--mtime', action='store_true', default=False,
        help="set mtime/author even when the root is up-to-date")
    parser.add_option('--profile',
        help="print profile information to the given file")
    parser.add_option(
        '--quick', action="store_true", default=False,
        help="do not check the database consistency.")

    # TODO Add option --pretend (to know whether the database needs to be
    # updated)

    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    target = args[0]

    # Action!
    if options.profile is not None:
        runctx("update(parser, options, target)", globals(), locals(),
               options.profile)
    else:
        update(parser, options, target)
