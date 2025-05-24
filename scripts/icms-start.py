#!/usr/bin/env python3
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from logging import getLogger
from optparse import OptionParser
import sys

from xapian import DatabaseLockError

# Import from itools
from itools import __version__

# Import from ikaaro
from ikaaro.server import Server


log = getLogger("ikaaro")

if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = f'itools {__version__}'
    description = (
        'Starts a web server that publishes the TARGET ikaaro instance to the '
        'world.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")
    parser.add_option(
        '-r', '--read-only', action="store_true", default=False,
        help="Start the server in read-only mode.")
    parser.add_option(
        '-p', '--port', default=None,
        help="Start the server on this port")
    parser.add_option(
        '--quick', action="store_true", default=False,
        help="Do not check the database consistency.")

    # Parse arguments
    options, args = parser.parse_args()
    n_args = len(args)
    if n_args != 1 and n_args != 2:
        parser.error('Wrong number of arguments.')

    # Set-up the server
    target = args[0]
    try:
        server = Server(target, read_only=options.read_only, port=options.port,
                        detach=options.detach)
    except (FileNotFoundError, LookupError):
        log.error(f"Error: {target} instance do not exists")
        sys.exit(1)
    except DatabaseLockError:
        log.error(f'Error: Database {target} is already opened')
        sys.exit(1)

    # Check server
    successfully_init = server.check_consistency(options.quick)
    if not successfully_init:
        sys.exit(1)
    # Start server
    server.start()
    # Ok
    sys.exit(0)
