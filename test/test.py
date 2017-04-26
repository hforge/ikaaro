# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from unittest import TestLoader, TestSuite, TextTestRunner

# Import from itools
from itools.core import get_abspath

# Import tests
import test_metadata
import test_server
from junitxml import JUnitXmlResult


test_modules = [test_metadata, test_server]


loader = TestLoader()

if __name__ == '__main__':
    usage = '%prog [OPTIONS]'
    description = 'Run ikaaro tests'
    parser = OptionParser(usage, description=description)
    parser.add_option('-m', '--mode', default='standard', help='tests mode')
    options, args = parser.parse_args()
    suite = TestSuite()
    for module in test_modules:
        suite.addTest(loader.loadTestsFromModule(module))
    if options.mode == 'standard':
        ret = TextTestRunner(verbosity=1).run(suite)
    elif options.mode == 'junitxml':
        path = get_abspath('./junit.xml')
        print('Result is here: %s' % path)
        f = file(path, 'wb')
        result = JUnitXmlResult(f)
        result.startTestRun()
        ret = suite.run(result)
        result.stopTestRun()
    exit_code = not ret.wasSuccessful()
    exit(exit_code)
