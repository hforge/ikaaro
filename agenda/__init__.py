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

# Import from ikaaro.agenda
from agenda import ConfigAgenda
from agenda_views import DailyView, MonthlyView, WeeklyView
from event import Event, EventModel, Event_Edit, Event_NewInstance
from event import Event_Render
from calendars import Calendar, Calendars_Enumerate, Calendars_View
from emails import Event_Reminder_Email


__all__ = [
    'Calendar',
    'Calendars_Enumerate',
    'Calendars_View',
    'Event',
    'EventModel',
    'DailyView',
    'MonthlyView',
    'WeeklyView',
    # Emails
    'Event_Reminder_Email']


# Register
register_document_type(Event)
register_skin('agenda', get_abspath('ui'))
Configuration.register_module(ConfigAgenda)

# Silent pyflakes
Event_Render, Event_Edit, Event_NewInstance
