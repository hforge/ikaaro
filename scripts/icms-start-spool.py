#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
import itools
from itools.utils import become_daemon

# Import from ikaaro
from ikaaro.spool import Spool
from ikaaro.update import is_instance_up_to_date


def start(optios, target):
    # Check instance is up to date
    if not is_instance_up_to_date(target):
        print 'The instance is not up-to-date, please type:'
        print
        print '    $ icms-update.py <instance>'
        print
        exit(1)

    spool = Spool(target)
    pid = spool.get_pid()
    if pid is not None:
        print '[%s] The Mail Spool is already running.' % target
        exit(1)

    print '[%s] Start Mail Spool.' % target
    # Detach: redirect standard file descriptors to '/dev/null'
    if options.detach:
        become_daemon()

    # Start
    spool.start()


if __name__ == '__main__':
    # The command line parser
    usage = '%prog TARGET'
    version = 'itools %s' % itools.__version__
    description = ('Starts a spool server')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option(
        '-d', '--detach', action="store_true", default=False,
        help="Detach from the console.")

    options, args = parser.parse_args()
    if len(args) == 0:
        parser.error('The TARGET argument is missing.')

    # Start the spool
    start(options, args[0])
