#!/usr/bin/env python3
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

import asyncio
import logging
import optparse
import sys

# Requirements
import xapian

# Import from itools
import itools

# Import from ikaaro
from ikaaro.server import Server, ask_confirmation

log = logging.getLogger("ikaaro")


async def update_catalog(target, options):
    # Check the server is not started, or started in read-only mode
    try:
        server = Server(target, read_only=False, cache_size=options.cache_size, detach=options.detach)
    except (FileNotFoundError, LookupError):
        log.error(f"Error: {target} instance do not exists")
        sys.exit(1)
    except xapian.DatabaseLockError:
        log.error(f'Error: Database {target} is already opened')
        sys.exit(1)

    # Ask
    message = 'Update the catalog (y/N)? '
    if ask_confirmation(message, options.confirm) is False:
        return

    # Server reindex
    await server.reindex_catalog(as_test=options.test, quiet=options.quiet, quick=options.quick)


if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = f'itools {itools.__version__}'
    description = (
        'Rebuilds the catalog: first removes and creates a new empty one;'
        ' then traverses and indexes all resources in the database.')
    parser = optparse.OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-y', '--yes', action='store_true', dest='confirm',
        help="start the update without asking confirmation")
    parser.add_option('--cache-size', default='400:600',
        help="define the size of the database cache (default 400:600)")
    parser.add_option('-q', '--quiet', action='store_true',
        help="be quiet")
    parser.add_option(
        '--quick', action="store_true", default=False,
        help="do not check the database consistency.")
    parser.add_option('-t', '--test', action='store_true', default=False,
        help="a test mode, don't stop the indexation when an error occurs")
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")

    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    target = args[0]

    # Action!
    asyncio.run(update_catalog(target, options))
