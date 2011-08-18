# -*- coding: UTF-8 -*-
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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

# Import from itools
from itools.core import get_abspath

# Import from ikaaro
from ikaaro.config import Configuration
from ikaaro.registry import register_document_type
from ikaaro.skins import register_skin
from ikaaro.root import Root

# Import from ikaaro.calendar
from calendar_ import ConfigCalendar
from calendar_views import MonthlyView, WeeklyView, DailyView
from calendar_views import Calendar_NewEvent
from event import Event, EventModel, Event_Edit, Event_NewInstance
from family import Calendar_Family, Calendar_FamiliesEnumerate


__all__ = [
    'Calendar_Family',
    'Calendar_FamiliesEnumerate',
    'Event',
    'EventModel',
    'MonthlyView',
    'WeeklyView']


# Register
register_document_type(Event)
register_skin('calendar', get_abspath('ui'))
Configuration.register_plugin(ConfigCalendar)
Root.monthly_view = MonthlyView()
Root.weekly_view = WeeklyView()
Root.daily_view = DailyView()
Root.new_event = Calendar_NewEvent()

# Silent pyflakes
Event_Edit, Event_NewInstance
