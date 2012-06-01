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
from sys import exit, stdout
from traceback import print_exc

# Import from itools
import itools
from itools.database import check_database
from itools.web import get_context

# Import from ikaaro
from ikaaro.resource_ import DBResource
from ikaaro.server import Server, ask_confirmation, get_config
from ikaaro.server import get_fake_context, get_pid, load_modules


# Monkey patch, so all resources are soft and we don't fail loading
DBResource.fields_soft = True



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
        # Skip up-to-date resources
        obj_version = resource.metadata.version
        cls_version = resource.class_version
        if obj_version == cls_version:
            continue

        # Check for code that is older than the instance
        if obj_version > cls_version:
            print
            print '* %s resource=%s class=%s' % (resource.abspath,
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
            paths = [resource.abspath]
        elif next_version == version:
            paths.append(resource.abspath)

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
            line = '%s %s\n' % (resource.abspath, resource.__class__)
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

    # Load the modules
    config = get_config(target)
    load_modules(config)

    #######################################################################
    # STAGE 1: Find out the versions to upgrade
    #######################################################################
    server = Server(target)
    database = server.database
    # Build a fake context
    context = get_fake_context(database)
    context.server = server
    context.init_context()
    # Local variables
    root = server.root

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
