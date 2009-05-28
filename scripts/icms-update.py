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
from optparse import OptionParser
from subprocess import Popen, call, PIPE
from sys import exit, stdout
from time import time
from traceback import print_exc

# Import from itools
import itools
from itools.core import start_subprocess
from itools.csv import Property
from itools.fs import lfs
from itools.web import get_context

# Import from ikaaro
from ikaaro.metadata import Metadata
from ikaaro.obsolete.metadata import Metadata as OldMetadata
from ikaaro.resource_ import DBResource
from ikaaro.server import Server, ask_confirmation, get_fake_context


def abort():
    print '*'
    print '* Upgrade process not finished!'
    print '*'
    exit(0)



def find_versions_to_update(root):
    print 'STAGE 2: Find next version to upgrade (may take a while).'
    version = None
    paths = None

    # Find out the versions to upgrade
    versions = set()
    for resource in root.traverse_resources():
        # Skip non-database resources
        if not isinstance(resource, DBResource):
            continue

        # Skip up-to-date resources
        obj_version = resource.metadata.get_property('version').value
        cls_version = resource.class_version
        if obj_version == cls_version:
            continue

        # Check for code that is older than the instance
        if obj_version > cls_version:
            print
            print '*'
            print '* ERROR: resource is newer than its class'
            print '* %s <%s>' % (resource.get_abspath(),
                                 resource.__class__.__name__)
            print '* %s > %s' % (obj_version, cls_version)
            print '*'
            exit(1)

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



def update_versions(target, database, version, paths, root):
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
        obj_version = resource.metadata.get_property('version').value
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
            path = resource.get_abspath()
            log.write('%s %s\n' % (path, resource.__class__))
            print_exc(file=log)
            log.write('\n')
            bad += 1
    # Commit
    get_context().git_message = u'Upgrade to version %s' % version
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
    server = Server(target)
    if server.is_running_in_rw_mode():
        print 'Cannot proceed, the server is running in read-write mode.'
        return

    #######################################################################
    # STAGE 0: Initialize '.git'
    # XXX Specific to the migration from 0.50 to 0.60
    #######################################################################
    path = '%s/database' % target
    if not database.fs.exists('.git'):
        message = 'STAGE 0: Add the Git archive (y/N)? '
        if ask_confirmation(message, confirm) is False:
            abort()
        # Init
        print 'STAGE 0: git init'
        command = ['git', 'init']
        call(command, cwd=path, stdout=PIPE)
        # Add
        print 'STAGE 0: git add (may take a while)'
        command = ['git', 'add', '.']
        t0 = time()
        call(command, cwd=path, stdout=PIPE)
        print '       : %f seconds' % (time() - t0)
        # Commit
        print 'STAGE 0: git commit'
        command = ['git', 'commit', '--author=nobody <>', '-m', 'First commit']
        t0 = time()
        p = Popen(command, cwd=path, stdout=PIPE)
        p.communicate()
        print '       : %f seconds' % (time() - t0)

    #######################################################################
    # STAGE 1: Change format of the metadata
    # XXX Specific to the migration from 0.60 to 0.65
    #######################################################################
    metadata = Metadata('%s/.metadata' % path)
    try:
        metadata.load_state()
    except SyntaxError:
        message = 'STAGE 1: Update metadata to the new format (y/N)? '
        if ask_confirmation(message, confirm) is False:
            abort()
        print 'STAGE 1: Updating metadata (may take a while)'
        t0 = time()
        for filename in lfs.traverse(path):
            if not filename.endswith('.metadata'):
                continue
            # Load the old metadata
            old_metadata = OldMetadata(filename)
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
                    error = 'unexpected "%s" property in "%s"'
                    raise NotImplementedError, error % (name, filename)
                else:
                    property = Property(value)
                    new_metadata.set_property(name, property)
            # Save
            del old_metadata
            lfs.remove(filename)
            new_metadata.save_state_to(filename)
        print '       : %f seconds' % (time() - t0)
        # Commit
        print 'STAGE 1: Committing changes to git (may take a while)'
        t0 = time()
        command = ['git', 'commit', '--author=nobody <>',
                   '-m', 'Update metadata to new format']
        p = Popen(command, cwd=path, stdout=PIPE)
        p.communicate()
        print '       : %f seconds' % (time() - t0)

    #######################################################################
    # STAGE 2: Find out the versions to upgrade
    #######################################################################
    # Build a fake context
    context = get_fake_context()
    server.init_context(context)
    # Local variables
    database = server.database
    root = server.root

    start_subprocess(path)
    version, paths = find_versions_to_update(root)
    while version:
        message = 'STAGE 2: Upgrade %d resources to version %s (y/N)? '
        message = message % (len(paths), version)
        if ask_confirmation(message, confirm) is False:
            abort()
        update_versions(target, database, version, paths, root)
        # Reset the state
        database.cache.clear()
        database.cache[root.metadata.key] = root.metadata
        print 'STAGE 2: Finish upgrading to version %s' % version
        version, paths = find_versions_to_update(root)

    print 'STAGE 2: Done.'

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
    parser.add_option(
        '-y', '--yes', action='store_true', dest='confirm',
        help="start the update without asking confirmation")
    parser.add_option('--profile',
        help="print profile information to the given file")

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
