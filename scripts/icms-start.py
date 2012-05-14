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
from sys import exit

# Import from itools
from itools import __version__
from itools.core import become_daemon
from itools.database import check_database
from itools.loop import Loop, cron

# Import from ikaaro
from ikaaro.update import is_instance_up_to_date
from ikaaro.server import Server, CMSContext, get_pid


def start(options, target):
    # Check the server is not running
    pid = get_pid('%s/pid' % target)
    if pid is not None:
        print '[%s] The Web Server is already running.' % target
        return 1
    # XXX Obsolete code, remove by 0.70
    sub_pid = get_pid('%s/pid-subprocess' % target)
    if sub_pid is not None:
        print ('[%s] The Web Server subprocess is running, please use '
               'icms-stop.py to stop it.') % target
        return 1

    # Check for database consistency
    if options.quick is False and check_database(target) is False:
        return 1

    # Check instance is up to date
    if not is_instance_up_to_date(target):
        print 'The instance is not up-to-date, please type:'
        print
        print '    $ icms-update.py %s' % target
        print
        return 1

    # Daemon mode
    if options.detach:
        become_daemon()

    # Set-up the server
    server = Server(target, read_only=options.read_only,
                    profile_space=options.profile_space)

    # Update Git tree-cache, to speed things up
    server.database.worktree.update_tree_cache()

    # Find out the IP to listen to
    config = server.config
    address = config.get_value('listen-address').strip()
    if not address:
        raise ValueError, 'listen-address is missing from config.conf'
    if address == '*':
        address = None

    # Find out the port to listen
    port = config.get_value('listen-port')
    if port is None:
        raise ValueError, 'listen-port is missing from config.conf'

    server.listen(address, port)
    server.set_context('/', CMSContext)
    interval = config.get_value('cron-interval')
    if interval:
        cron(server.cron_manager, 1)

    # Run
    profile = options.profile_time
    profile = ('%s/log/profile' % target) if profile else None
    loop = Loop(pid_file='%s/pid' % target, profile=profile)
    loop.run()

    # Ok
    return 0


if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % __version__
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
        '--quick', action="store_true", default=False,
        help="Do not check the database consistency.")
    parser.add_option(
        '--profile-time', action="store_true", default=False,
        help="Write profile information tot the 'log/profile' file.")
    parser.add_option(
        '--profile-space', action="store_true", default=False,
        help="Enable remote monitoring by guppy, http://guppy-pe.sf.net/")

    # Parse arguments
    options, args = parser.parse_args()
    n_args = len(args)
    if n_args != 1:
        parser.error('Wrong number of arguments.')

    # Start server
    target = args[0]
    ret = start(options, target)
    exit(ret)

