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
from ikaaro.website import WebSite

# Import from ikaaro.calendar
from calendar_ import ConfigCalendar
from calendar_views import MonthlyView, WeeklyView, DailyView
from event import Event


__all__ = [
    'Event',
    'MonthlyView',
    'WeeklyView']


# Register
register_document_type(Event)
register_skin('calendar', get_abspath('ui'))
Configuration.register_plugin(ConfigCalendar)
WebSite.monthly_view = MonthlyView()
WebSite.weekly_view = WeeklyView()
WebSite.daily_view = DailyView()
