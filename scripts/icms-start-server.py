#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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
from optparse import OptionParser
import sys

# Import from itools
import itools
from itools import vfs

# Import from ikaaro
from ikaaro.server import Server
from ikaaro.update import is_instance_up_to_date


def start(options, target):
    # Check for database consistency
    if vfs.exists('%s/database.commit' % target):
        print 'The database is not in a consistent state, to fix it up type:'
        print
        print '    $ icms-restore.py <instance>'
        print
        return

    # Check instance is up to date
    if not is_instance_up_to_date(target):
        print 'The instance is not up-to-date, please type:'
        print
        print '    $ icms-update.py <instance>'
        print
        return

    # Set-up the server
    server = Server(target, options.address, options.port, options.debug)

    # Check the server is not running
    pid = server.get_pid()
    if pid is not None:
        print '[%s] The Web Server is already running.' % target
        return

    address = server.address or '*'
    port = server.port
    print '[%s] Web Server listens %s:%s' % (target, address, port)
    sys.stdout.flush()
    server.start()


if __name__ == '__main__':
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % itools.__version__
    description = ('Starts a web server that publishes the TARGET ikaaro'
                   ' instance to the world. If several TARGETs are given, one'
                   ' server will be started for each one (in this mode no'
                   ' options are available).')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option('-a', '--address', help='listen to IP ADDRESS')
    parser.add_option('-p', '--port', type='int', help='listen to PORT number')
    parser.add_option('', '--debug', action="store_true", default=False,
                      help="Start the server on debug mode.")
    options, args = parser.parse_args()
    if len(args) == 0:
        parser.error('The TARGET argument is missing.')

    # Start the server
    start(options, args[0])

