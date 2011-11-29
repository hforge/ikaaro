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

    options = [
        {'name':'1', 'value': MSG(u'Monday'), 'shortname': 'MO'},
        {'name':'2', 'value': MSG(u'Tuesday'), 'shortname': 'TU'},
        {'name':'3', 'value': MSG(u'Wednesday'), 'shortname': 'WE'},
        {'name':'4', 'value': MSG(u'Thursday'), 'shortname': 'TH'},
        {'name':'5', 'value': MSG(u'Friday'), 'shortname': 'FR'},
        {'name':'6', 'value': MSG(u'Saturday'), 'shortname': 'SA'},
        {'name':'7', 'value': MSG(u'Sunday'), 'shortname': 'SU'}]

    @classmethod
    def get_shortname(cls, name):
        for option in cls.options:
            if option['name'] == name:
                return option['shortname']


    @classmethod
    def get_name_by_shortname(cls, shortname):
        for option in cls.options:
            if option['shortname'] == shortname:
                return option['name']



class IntegerRange(Enumerate):
    count = 4

    @classmethod
    def get_options(cls):
        return [
            {'name': str(i), 'value': str(i)} for i in range(1, cls.count) ]



class Days(IntegerRange):
    count = 32



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
