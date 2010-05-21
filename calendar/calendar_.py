# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2010 Alexis Huet <alexis@itaapy.com>
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
from itools.core import merge_dicts
from itools.csv import Property, property_to_str
from itools.datatypes import DataType, Date, String, Unicode
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.file_views import File_View
from ikaaro.folder import Folder
from calendar_views import Calendar_Import, Calendar_Export
from calendar_views import MonthlyView, TimetablesForm, WeeklyView, DailyView
from event import Event


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



class Calendar(Folder):

    class_id = 'calendarTable'
    class_title = MSG(u'Calendar')
    class_description = MSG(u'Schedule your time with calendar files.')
    class_icon16 = 'icons/16x16/icalendar.png'
    class_icon48 = 'icons/48x48/icalendar.png'
    class_views = ['monthly_view', 'weekly_view', 'daily_view',
                   'edit_timetables', 'import_', 'export_form']

    timetables = [((7,0),(8,0)), ((8,0),(9,0)), ((9,0),(10,0)),
                  ((10,0),(11,0)), ((11,0),(12,0)), ((12,0),(13,0)),
                  ((13,0),(14,0)), ((14,0),(15,0)), ((15,0),(16,0)),
                  ((16,0),(17,0)), ((17,0),(18,0)), ((18,0),(19,0)),
                  ((19,0),(20,0)), ((20,0),(21,0))]


    def get_new_id(self):
        ids = [ int(x) for x in self.get_names()]
        return str(max(ids) + 1) if ids else '0'


    class_schema = merge_dicts(
        Folder.class_schema,
        timetables=Timetables(source='metadata'))


    def get_document_types(self):
        return [Event]


    #######################################################################
    # User Interface
    #######################################################################
    def get_action_url(self, **kw):
        if 'day' in kw:
            return ';new_resource?type=event&date=%s' % Date.encode(kw['day'])
        if 'id' in kw:
            return '%s/;edit' % kw['id']

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
            timetables.append(((start[0], start[1]), (end[0], end[1])))
        return timetables


    def to_ical(self):
        """Serialize as an ical file, generally named .ics
        """
        ikaaro_to_ics = [
            ('dtstart', 'DTSTART'),
            ('dtend', 'DTEND'),
            ('status', 'STATUS'),
            ('title', 'SUMMARY'),
            ('description', 'DESCRIPTION'),
            ('location', 'LOCATION'),
            ('mtime', 'UID')]

        lines = ['BEGIN:VCALENDAR\n',
                'VERSION:2.0\n',
                'PRODID:-//itaapy.com/NONSGML ikaaro icalendar V1.0//EN\n']

        # Calendar components
        for event in self._get_names():
            event = self._get_resource(event)
            if event is not None:
                if not isinstance(event, Event):
                    raise TypeError('%s instead of %s' % (type(event), Event))
                lines.append('BEGIN:VEVENT\n')
                for ikaaro_name, ics_name in ikaaro_to_ics:
                    datatype = event.get_property_datatype(ikaaro_name)
                    property = event.metadata.get_property(ikaaro_name)
                    if property:
                        lang = property.get_parameter('lang')
                        if lang:
                            property = Property(property.value, LANGUAGE=lang)
                        p_schema = {'LANGUAGE': String(multiple=False)}
                        line = property_to_str(ics_name, property, datatype,
                                p_schema)
                        lines.append(line)
                lines.append('END:VEVENT\n')
        lines.append('END:VCALENDAR\n')

        return ''.join(lines)


    # Views
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    daily_view = DailyView()
    edit_timetables = TimetablesForm()
    export = Calendar_Export()
    import_ = Calendar_Import()
    export_form = File_View(title=MSG(u'Export'),
                            template='/ui/calendar/export_form.xml')
