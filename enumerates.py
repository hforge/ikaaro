# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from standard library
from datetime import date

# Import from itools
from itools.datatypes import Enumerate
from itools.gettext import MSG

days = {
    0: MSG(u'Monday'),
    1: MSG(u'Tuesday'),
    2: MSG(u'Wednesday'),
    3: MSG(u'Thursday'),
    4: MSG(u'Friday'),
    5: MSG(u'Saturday'),
    6: MSG(u'Sunday')}


class DaysOfWeek(Enumerate):

    @classmethod
    def get_options(cls):
        options = []
        for i in range(1, 8):
            options.append({'name': str(i), 'value': days[i-1]})
        return options



class Days(Enumerate):

    @classmethod
    def get_options(cls):
        options = []
        for i in range(1, 32):
            options.append({'name': str(i), 'value': str(i)})
        return options



class Months(Enumerate):

    options = [
        {'name': '1', 'value': MSG(u'January')},
        {'name': '2', 'value': MSG(u'February')},
        {'name': '3', 'value': MSG(u'March')},
        {'name': '4', 'value': MSG(u'April')},
        {'name': '5', 'value': MSG(u'May')},
        {'name': '6', 'value': MSG(u'June')},
        {'name': '7', 'value': MSG(u'July')},
        {'name': '8', 'value': MSG(u'August')},
        {'name': '9', 'value': MSG(u'September')},
        {'name': '10', 'value': MSG(u'October')},
        {'name': '11', 'value': MSG(u'November')},
        {'name': '12', 'value': MSG(u'December')}]



class Years(Enumerate):

    start = 1900

    @classmethod
    def get_options(cls):
        options = []
        for d in range(cls.start, date.today().year):
            options.append({'name': str(d), 'value': str(d)})
        return options
