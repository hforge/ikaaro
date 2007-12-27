#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from optparse import OptionParser
import sys
from traceback import print_exc

# Import from itools
import itools
from itools import vfs
from itools.web import set_context, Context

# Import from ikaaro
from ikaaro.base import DBObject
from ikaaro.server import Server, ask_confirmation


def update(parser, options, target):
    folder = vfs.open(target)
    confirm = options.confirm

    #######################################################################
    # STAGE 0: Specific upgrades
    #######################################################################
    # Move the log files (FIXME Remove by 0.21)
    if not folder.exists('log'):
        message = 'Move log files to the log folder (y/N)? '
        if ask_confirmation(message, confirm) is False:
            return
        folder.make_folder('log')
        for name in 'access', 'error', 'debug', 'spool', 'spool_error':
            if folder.exists('%s_log' % name):
                folder.move('%s_log' % name, 'log/%s' % name)

    # Move the "catalog/fields" file (FIXME Remove by 0.21)
    if folder.exists('catalog/fields'):
        message = 'Move "catalog/fields" file to "catalog/data/fields" (y/N)? '
        if ask_confirmation(message, confirm) is False:
            return
        folder.move('catalog/fields', 'catalog/data/fields')

    #######################################################################
    # STAGE 1: Find out the versions to upgrade
    #######################################################################
    print '*'
    print '* Please wait while we find out the versions to upgrade.'

    # Build the server object
    server = Server(target)
    database = server.database
    root = server.root

    # Find out the versions to upgrade
    versions = set()
    for object in root.traverse_objects():
        # Skip non-database objects
        if not isinstance(object, DBObject):
            continue

        # Skip up-to-date objects
        obj_version = object.metadata.version
        cls_version = object.class_version
        if obj_version == cls_version:
            continue

        # Check for code that is older than the instance
        if obj_version > cls_version:
            print '*'
            print '* ERROR: object is newer than its class'
            print '* %s <%s>' % (object.abspath, object.__class__.__name__)
            print '* %s > %s' % (obj_version, cls_version)
            print '*'
            return

        for version in object.get_next_versions():
            versions.add(version)

    versions = list(versions)
    versions.sort()

    print '* Versions to upgrade: %s' % ', '.join(versions)
    print '*'

    #######################################################################
    # STAGE 2: General Upgrade code
    #######################################################################
    # Build a fake context
    context = Context(None)
    context.server = server
    set_context(context)

    # Open the update log
    log = open('%s/log/update' % target, 'w')

    # Update
    for version in versions:
        message = 'Upgrade to version %s (y/N)? ' % version
        if ask_confirmation(message, confirm) is False:
            print '*'
            print '* WARNING: Upgrade process not finished.'
            print '*'
            return
        # Go ahead
        bad = 0
        for object in root.traverse_objects():
            # Skip non-database objects
            if not isinstance(object, DBObject):
                continue

            # Skip up-to-date objects
            obj_version = object.metadata.version
            cls_version = object.class_version
            if obj_version == cls_version:
                continue

            next_versions = object.get_next_versions()
            if not next_versions:
                continue

            if next_versions[0] != version:
                continue

            # Update
            sys.stdout.write('.')
            sys.stdout.flush()
            try:
                object.update(version)
                database.save_changes()
            except:
                path = object.get_abspath()
                log.write('%s <%s>\n' % (path, object.__class__.__name__))
                print_exc(file=log)
                log.write('\n')
                bad += 1
        # Stop if there were errors
        print
        if bad > 0:
            print '*'
            print '* ERROR: %s objects failed to upgrade to version %s' \
                  % (bad, version)
            print '* Check the "%s/log/update" file.' % target
            print '*'
            return

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

    # TODO Add option --pretend (to know whether the database needs to be
    # updated)

    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    target = args[0]

    # Action!
    update(parser, options, target)
