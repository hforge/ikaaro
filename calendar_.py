# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from Standard Library
from datetime import time

# Import from itools
from itools.datatypes import DataType, Date
from itools.gettext import MSG
from itools.ical import iCalendar, icalendarTable
from itools.ical import Record
from itools.web import get_context

# Import from ikaaro
from calendar_views import Calendar_Upload, Calendar_Download
from calendar_views import AddEventForm, EditEventForm
from calendar_views import MonthlyView, TimetablesForm, WeeklyView, DailyView
from file_views import File_View
from folder import Folder
from registry import register_resource_class
from resource_ import DBResource
from table import Table
from text import Text


class Timetables(DataType):
    """Timetables are tuples of time objects (start, end) used by cms.ical.

    Example with 3 timetables as saved into metadata:
        (8,0),(10,0);(10,0),(12,0);(15,30),(17,30)

    Decoded value are:
        [(time(8,0), time(10,0)), (time(10,0), time(12, 0)),
         (time(15,30), time(17, 30))]
    """

    default = ()

    @staticmethod
    def decode(value):
        if not value:
            return ()
        timetables = []
        for timetable in value.strip().split(';'):
            start, end = timetable[1:-1].split('),(')
            hours, minutes = start.split(',')
            hours, minutes = int(hours), int(minutes)
            start = time(hours, minutes)
            hours, minutes = end.split(',')
            hours, minutes = int(hours), int(minutes)
            end = time(hours, minutes)
            timetables.append((start, end))
        return tuple(timetables)


    @staticmethod
    def encode(value):
        timetables = []
        for start, end in value:
            start = '(' + str(start.hour) + ',' + str(start.minute) + ')'
            end = '(' + str(end.hour) + ',' + str(end.minute) + ')'
            timetables.append(start + ',' + end)
        return ';'.join(timetables)



class CalendarBase(DBResource):

    class_title = MSG(u'Calendar')
    class_description = MSG(u'Schedule your time with calendar files.')
    class_icon16 = 'icons/16x16/icalendar.png'
    class_icon48 = 'icons/48x48/icalendar.png'
    class_views = ['monthly_view', 'weekly_view', 'daily_view',
                   'edit_timetables', 'upload', 'download_form']


    timetables = [((7,0),(8,0)), ((8,0),(9,0)), ((9,0),(10,0)),
                  ((10,0),(11,0)), ((11,0),(12,0)), ((12,0),(13,0)),
                  ((13,0),(14,0)), ((14,0),(15,0)), ((15,0),(16,0)),
                  ((16,0),(17,0)), ((17,0),(18,0)), ((18,0),(19,0)),
                  ((19,0),(20,0)), ((20,0),(21,0))]


    def get_calendars(self):
        return [self]


    def get_action_url(self, **kw):
        if 'day' in kw:
            return ';add_event?date=%s' % Date.encode(kw['day'])
        if 'id' in kw:
            return ';edit_event?id=%s' % kw['id']

        return None


    # Test if user in context is the organizer of a given event (or is admin)
    def is_organizer_or_admin(self, context, event):
        if self.get_access_control().is_admin(context.user, self):
            return True
        if event:
            organizer = event.get_property('ORGANIZER')
            user_path = str(context.user.get_abspath())
            return organizer and user_path == organizer.value
        ac = self.parent.get_access_control()
        return ac.is_allowed_to_edit(context.user, self.parent)


    def get_timetables(self):
        """Build a list of timetables represented as tuples(start, end).
        Data are taken from metadata or from class value.

        Example of metadata:
          <timetables>(8,0),(10,0);(10,30),(12,0);(13,30),(17,30)</timetables>
        """
        if self.has_property('timetables'):
            return self.get_property('timetables')

        # From class value
        timetables = []
        for index, (start, end) in enumerate(self.timetables):
            timetables.append((time(start[0], start[1]), time(end[0], end[1])))
        return timetables


    def get_events_to_display(self, start, end):
        file = self.handler
        events = []
        for event in file.search_events_in_range(start, end, sortby='date'):
            e_dtstart = event.get_property('DTSTART').value
            events.append((self.name, e_dtstart, event))
        events.sort(lambda x, y : cmp(x[1], y[1]))
        return {self.name: 0}, events


    #######################################################################
    # Views
    #######################################################################
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    daily_view = DailyView()
    add_event = AddEventForm()
    edit_event = EditEventForm()
    edit_timetables = TimetablesForm()
    download = Calendar_Download()
    upload = Calendar_Upload()
    download_form = File_View()



class CalendarTable(CalendarBase, Table):

    class_id = 'calendarTable'
    class_version = '20071216'
    class_handler = icalendarTable
    record_class = Record


    def get_record(self, id):
        id = int(id)
        return self.handler.get_record(id)


    def add_record(self, type, properties):
        properties['type'] = type
        # Reindex the resource
        get_context().server.change_resource(self)
        return self.handler.add_record(properties)


    def update_record(self, id, properties):
        id = int(id)
        self.handler.update_record(id, **properties)
        # Reindex the resource
        get_context().server.change_resource(self)


    def _remove_event(self, uid):
        self.handler.del_record(int(uid))
        # Reindex the resource
        get_context().server.change_resource(self)


    @classmethod
    def get_metadata_schema(cls):
        schema = Table.get_metadata_schema()
        schema['timetables'] = Timetables
        return schema


    # Use edit_event instead
    edit_record = None



class Calendar(CalendarBase, Text):

    class_id = 'text/calendar'
    class_version = '20071216'
    class_handler = iCalendar


    def get_record(self, id):
        return self.handler.get_record(id)


    def add_record(self, type, properties):
        # Reindex the resource
        get_context().server.change_resource(self)
        return self.handler.add_component(type, **properties)


    def update_record(self, id, properties):
        self.handler.update_component(id, **properties)
        # Reindex the resource
        get_context().server.change_resource(self)


    def _remove_event(self, uid):
        self.handler.remove(uid)
        # Reindex the resource
        get_context().server.change_resource(self)


    @classmethod
    def get_metadata_schema(cls):
        schema = Text.get_metadata_schema()
        schema['timetables'] = Timetables
        return schema



class CalendarContainer(CalendarBase):

    @classmethod
    def get_metadata_schema(cls):
        return {'timetables': Timetables}


    def get_calendars(self, types=None):
        """List of sources from which taking events.
        """
        if types is None:
            types = (Calendar, CalendarTable)

        if isinstance(self, Folder):
            calendars = self.search_resources(cls=types)
            return list(calendars)
        return [self]


    # Views
    download = None
    upload = None



###########################################################################
# Register
###########################################################################
register_resource_class(CalendarTable)
register_resource_class(Calendar)
