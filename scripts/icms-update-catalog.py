#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
import itools
from itools.core import start_subprocess



def update_catalog(parser, options, target):
    # Imports
    import sys
    from time import time
    from itools.core import vmsize
    from itools.fs import lfs
    from itools.xapian import make_catalog, CatalogAware
    from ikaaro.boot import get_server
    from ikaaro.database import check_database
    from ikaaro.server import ask_confirmation, is_running_in_rw_mode
    from ikaaro.registry import get_register_fields

    # Check the server is not started, or started in read-only mode
    server = get_server(target, options.cache_size, True)
    if is_running_in_rw_mode():
        print 'Cannot proceed, the server is running in read-write mode.'
        return

    # Check for database consistency
    if options.quick is False and check_database(target) is False:
        return 1

    # Ask
    message = 'Update the catalog (y/N)? '
    if ask_confirmation(message, options.confirm) is False:
        return

    # Create a temporary new catalog
    catalog_path = '%s/catalog.new' % target
    if lfs.exists(catalog_path):
        lfs.remove(catalog_path)
    catalog = make_catalog(catalog_path, get_register_fields())

    # Build a fake context
    app = server.get_mount('/')
    context = app.get_fake_context()

    # Update
    root = context.get_resource('/')
    t0, v0 = time(), vmsize()
    doc_n = 0
    for obj in root.traverse_resources():
        if not issubclass(obj, CatalogAware):
            continue
        if not options.quiet:
            print doc_n, obj.get_abspath()
        doc_n += 1
        context.resource = obj
        catalog.index_document(obj)
        # Free Memory
        del obj
        app.database.make_room()
    # Update / Report
    t1, v1 = time(), vmsize()
    v = (v1 - v0)/1024
    print '[Update] Time: %.02f seconds. Memory: %s Kb' % (t1 - t0, v)

    # Commit
    print '[Commit]',
    sys.stdout.flush()
    catalog.save_changes()
    # Commit / Replace
    old_catalog_path = '%s/catalog' % target
    if lfs.exists(old_catalog_path):
        lfs.remove(old_catalog_path)
    lfs.move(catalog_path, old_catalog_path)
    # Commit / Report
    t2, v2 = time(), vmsize()
    v = (v2 - v1)/1024
    print 'Time: %.02f seconds. Memory: %s Kb' % (t2 - t1, v)



if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % itools.__version__
    description = (
        'Rebuilds the catalog: first removes and creates a new empty one;'
        ' then traverses and indexes all resources in the database.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-y', '--yes', action='store_true', dest='confirm',
        help="start the update without asking confirmation")
    parser.add_option('--profile',
        help="print profile information to the given file")
    parser.add_option('--cache-size', default='400:600',
        help="define the size of the database cache (default 400:600)")
    parser.add_option('-q', '--quiet', action='store_true',
        help="be quiet")
    parser.add_option(
        '--quick', action="store_true", default=False,
        help="Do not check the database consistency.")

    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    target = args[0]

    # Action!
    start_subprocess('%s/database' % target)
    if options.profile is not None:
        from cProfile import runctx
        runctx("update_catalog(parser, options, target)", globals(), locals(),
               options.profile)
    else:
        update_catalog(parser, options, target)
