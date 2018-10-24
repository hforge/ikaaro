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
from sys import exit

# Import from itools
import itools

# Import from ikaaro
from ikaaro.update import do_run_next_update_method
from ikaaro.server import Server
from ikaaro.server import get_pid


def update(parser, options, target):
    # Check the server is not started, or started in read-only mode
    pid = get_pid('%s/pid' % target)
    if pid is not None:
        print('Cannot proceed, the server is running in read-write mode.')
        return
    # Load server
    server = Server(target)
    # Build a fake context
    with server.database.init_context() as context:
        print('STAGE 1: Find out the versions to upgrade (may take a while).')
        msgs = do_run_next_update_method(context, force=options.force)
        print(u'\n'.join([x.gettext() for x in msgs]))



if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % itools.__version__
    description = ('Updates the TARGET ikaaro instance (if needed). Use'
                   ' this command when upgrading to a new version of itools.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option('--force', action='store_true', default=False,
        help="continue the upgrade process in spite of errors")
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
    # Ok
    exit(0)
