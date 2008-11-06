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
from subprocess import Popen
from sys import argv, exit
from os.path import dirname, join, realpath
from time import sleep

# Import from itools
import itools

# Import from ikaaro
from ikaaro.update import is_instance_up_to_date



def start(parser, options, target):
    # Check instance is up to date
    if not is_instance_up_to_date(target):
        print 'The instance is not up-to-date, please type:'
        print
        print '    $ icms-update.py <instance>'
        print
        return

    # Start Server
    script_path = dirname(realpath(argv[0]))
    path_icms_start_server = join(script_path, 'icms-start-server.py')
    args = [path_icms_start_server, target]
    if options.debug:
        args.append('--debug')
    if options.detach:
        args.append('--detach')
    if options.port:
        args.append('--port=%s' % options.port)
    if options.address:
        args.append('--address=%s' % options.address)
    args = ' '.join(args)
    p_server = Popen(args, shell=True)

    # Start the Mail Spool
    path_icms_start_spool = join(script_path, 'icms-start-spool.py')
    args = [path_icms_start_spool, target]
    if options.detach:
        args.append('--detach')
    args = ' '.join(args)
    p_spool = Popen(args, shell=True)

    # Detach
    if options.detach:
        sleep(2)
        exit(abs(p_server.poll() or 0)+abs(p_spool.poll() or 0))

    # Do not detach: wait for the child process
    try:
        ret = p_server.wait()
    except:
        ret = 1
    exit(abs(ret or 0)+abs(p_spool.poll() or 0))



if __name__ == '__main__':
    # The command line parser
    usage = ('%prog [OPTIONS] TARGET\n'
             '       %prog TARGET [TARGET]*')
    version = 'itools %s' % itools.__version__
    description = ('Starts a web server that publishes the TARGET ikaaro'
                   ' instance to the world. If several TARGETs are given, one'
                   ' server will be started for each one (in this mode no'
                   ' options are available).')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-a', '--address', help='listen to IP ADDRESS')
    parser.add_option(
        '', '--debug', action="store_true", default=False,
        help="Start the server on debug mode.")
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")
    parser.add_option(
        '-p', '--port', type='int', help='listen to PORT number')

    options, args = parser.parse_args()
    n_args = len(args)
    if n_args == 0:
        parser.error('The TARGET argument is missing.')
    elif n_args == 1:
        pass
    elif options.address or options.debug or options.detach or options.port:
        parser.error('Options are not available when starting several '
                     'servers at once.')

    # Action!
    for target in args:
        start(parser, options, target)
