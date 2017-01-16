# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2011 Nicolas Deram <nicolas@itaapy.com>
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
from datetime import date, timedelta

# Import from itools
from itools.datatypes import Date, Enumerate
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.autoform import SelectWidget
from ikaaro.datatypes import DaysOfWeek, IntegerRange
from ikaaro.fields import Date_Field, Select_Field
from ikaaro.utils import make_stl_template


###########################################################################
# Code to calculate the dates
###########################################################################
# Recurrence
MAX_DELTA = timedelta(3650) # we cannot index an infinite number of values

def next_day(x, delta=timedelta(1)):
    return x + delta

def next_week(x):
    return x + timedelta(7 - x.weekday())

def next_month(x):
    year = x.year
    month = x.month + 1
    if month == 13:
        month = 1
        year = year + 1
    # FIXME handle invalid dates (like 31 April)
    return date(year, month, x.day)

def next_year(x):
    # FIXME handle 29 February
    return date(x.year + 1, x.month, x.day)


rrules = {
    'daily': next_day,
    'weekly': next_week,
    'monthly': next_month,
    'yearly': next_year}


def get_dates(start, end, rrule):
    dates = set()
    days = range((end - start).days + 1)
    f = lambda date: dates.update([ date + timedelta(x) for x in days ])

    # Case 1: No recurrence rule
    if not rrule or not rrule.value:
        f(start)
        return dates

    # Case 2: Recurrence rule
    rrule_name = rrule.value
    rrule_interval = int(rrule.get_parameter('interval') or 1)
    bydays = rrule.get_parameter('byday')
    if bydays:
        bydays = [ int(DaysOfWeek.get_name_by_shortname(v))
                   for v in bydays ]

    until = rrule.get_parameter('until')
    if until:
        until += timedelta(1)
    else:
        until = max(start, date.today()) + MAX_DELTA

    next_date = rrules[rrule_name]
    while start < until:
        interval = rrule_interval
        if bydays:
            # Check any day of byday parameter
            for byday in bydays:
                # Skip previous byday values
                if start.isoweekday() > byday:
                    continue
                # Go ahead to current byday value
                while start.isoweekday() < byday:
                    start = next_day(start)
                if start >= until:
                    break
                # Add current day (== byday value)
                f(start)
        else:
            f(start)
        # Go to next date based on rrule value and interval
        while interval > 0:
            start = next_date(start)
            interval -= 1

    return dates



###########################################################################
# Datatypes, Widgets and Fields
###########################################################################
class RRuleInterval_Datatype(IntegerRange):
    count = 31
    default = '1'


class RRuleInterval_Widget(SelectWidget):

    template = '/ui/agenda/rrule_interval_widget.xml'



class RRuleInterval_Field(Select_Field):

    title = MSG(u'Every')
    datatype = RRuleInterval_Datatype
    has_empty_option = False
    widget = RRuleInterval_Widget



class RRuleUntil_Datatype(Date):
    pass



class RRuleUntil_Field(Date_Field):

    title = MSG(u'Until')
    datatype = RRuleUntil_Datatype



class RRule_Datatype(Enumerate):

    options = [
        {'name': 'daily', 'value': MSG(u'Daily')},
        {'name': 'weekly', 'value': MSG(u'Weekly')},
        {'name': 'monthly', 'value': MSG(u'Monthly')},
        {'name': 'yearly', 'value': MSG(u'Yearly')}]


class RRule_Widget(SelectWidget):

    template = make_stl_template("""
    <select id="${id}" name="${name}" multiple="${multiple}" size="${size}"
      class="${css}" onchange="update_rrule_parameters();">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>
    <script>
     <![CDATA[
       $(document).ready(function(){
         update_rrule_parameters();
       });
     ]]>
    </script>""")


class RRule_Field(Select_Field):
    """Recurrence Rule
        - byday allowed on value 'weekly' only
        - default byday is MO,TU,WE,TH,FR,SA,SU
        - interval not allowed on value 'daily'
        - default interval is 1

        Examples:
            rrule;byday=MO,WE,FR;interval=1:weekly
            rrule;interval=2:monthly
    """
    datatype = RRule_Datatype
    parameters_schema = {'interval': RRuleInterval_Datatype,
                         'byday': DaysOfWeek(multiple=True),
                         'until': RRuleUntil_Datatype}
    widget = RRule_Widget
