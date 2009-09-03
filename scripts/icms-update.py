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
from os import devnull
from subprocess import Popen, call, PIPE
from sys import exit, stdout
from time import time
from traceback import print_exc

# Import from itools
import itools
from itools.core import start_subprocess
from itools import vfs
from itools.web import get_context

# Import from ikaaro
from ikaaro.resource_ import DBResource
from ikaaro.server import Server, ask_confirmation, get_fake_context


def abort():
    print '*'
    print '* Upgrade process not finished!'
    print '*'
    exit(0)



def find_versions_to_update(root):
    print 'STAGE 1: Find next version to upgrade (may take a while).'
    version = None
    resources = None

    # Find out the versions to upgrade
    versions = set()
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
            resources = [resource]
        elif next_version == version:
            resources.append(resource)

    return version, resources



def update_versions(target, database, version, resources):
    """Update the database to the given versions.
    """
    # Open the update log
    log = open('%s/log/update' % target, 'w')

    # Update
    bad = 0
    for resource in resources:
        # Skip non-database resources
        if not isinstance(resource, DBResource):
            continue

        # Skip up-to-date resources
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
    folder = vfs.open(target)
    confirm = options.confirm

    # Check the server is not started, or started in read-only mode
    server = Server(target)
    if server.is_running_in_rw_mode():
        print 'Cannot proceed, the server is running in read-write mode.'
        return

    # Build a fake context
    context = get_fake_context()
    server.init_context(context)
    # Local variables
    database = server.database
    root = server.root

    #######################################################################
    # STAGE 0: Initialize '.git'
    # XXX Specific to the migration from 0.50 to 0.60
    #######################################################################
    if not vfs.exists('%s/.git' % database.path):
        message = 'STAGE 0: Add the Git archive (y/N)? '
        if ask_confirmation(message, confirm) is False:
            abort()
        # Init
        print 'STAGE 0: git init'
        command = ['git', 'init']
        call(command, cwd=database.path, stdout=PIPE)
        # Add
        print 'STAGE 0: git add (may take a while)'
        command = ['git', 'add', '.']
        t0 = time()
        call(command, cwd=database.path, stdout=PIPE)
        print '       : %f seconds' % (time() - t0)
        # Commit
        print 'STAGE 0: git commit'
        command = ['git', 'commit', '--author=nobody <>', '-m', 'First commit']
        t0 = time()
        p = Popen(command, cwd=database.path, stdout=PIPE)
        p.communicate()
        print '       : %f seconds' % (time() - t0)

    #######################################################################
    # STAGE 1: Find out the versions to upgrade
    #######################################################################
    start_subprocess('%s/database' % target)
    version, resources = find_versions_to_update(root)
    while version:
        message = 'STAGE 1: Upgrade %d resources to version %s (y/N)? '
        message = message % (len(resources), version)
        if ask_confirmation(message, confirm) is False:
            abort()
        update_versions(target, database, version, resources)
        # Reset the state
        database.cache.clear()
        database.cache[root.metadata.uri] = root.metadata
        print 'STAGE 1: Finish upgrading to version %s' % version
        version, resources = find_versions_to_update(root)

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
