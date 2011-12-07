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
from itools.csv import Property, property_to_str
from itools.csv.table import get_tokens, read_name, unfold_lines
from itools.datatypes import String
from itools.gettext import MSG
from itools.ical import iCalendar

# Import from ikaaro
from ikaaro.config_common import NewResource_Local
from ikaaro.fields import Char_Field
from ikaaro.folder import Folder
from agenda_views import Calendar_Export, Calendar_ExportForm
from agenda_views import Calendar_Import, TimetablesForm
from agenda_views import MonthlyView, WeeklyView, DailyView
from agenda_views import Calendar_NewEvent
from calendars import Calendar, Calendars_View
from event import Event


ikaaro_to_ics = [
    ('dtstart', 'DTSTART'),
    ('dtend', 'DTEND'),
    ('status', 'STATUS'),
    ('title', 'SUMMARY'),
    ('description', 'DESCRIPTION'),
    ('location', 'LOCATION'),
    ('uid', 'UID'),
    ('mtime', 'LAST-MODIFIED')]

ics_to_ikaaro = dict([(y, x) for x, y in ikaaro_to_ics])


class Timetables(String):
    """Timetables are tuples of time objects (start, end) used by cms.ical.

    Example with 3 timetables as saved into metadata:
        timetables:8:0 10:0
        timetables:10:0 12:0
        timetables:15:30 17:30

    Decoded value are:
        [(time(8,0), time(10,0)), (time(10,0), time(12, 0)),
         (time(15,30), time(17, 30))]
    """

    @staticmethod
    def decode(value):
        if not value:
            return None

        start, end = value.split()
        hours, minutes = start.split(':')
        hours, minutes = int(hours), int(minutes)
        start = time(hours, minutes)
        hours, minutes = end.split(':')
        hours, minutes = int(hours), int(minutes)
        end = time(hours, minutes)
        return (start, end)


    @staticmethod
    def encode(value):
        print value
        start, end = value
        template = '%s:%s %s:%s'
        return template % (start.hour, start.minute, end.hour, end.minute)



class ConfigAgenda(Folder):

    class_id = 'agenda'
    class_version = '20110606'
    class_title = MSG(u'Agenda')
    class_description = MSG(u'Schedule your time with calendar files.')
    class_icon16 = 'icons/16x16/calendar.png'
    class_icon48 = 'icons/48x48/calendar.png'
    class_views = [
        'monthly_view', 'weekly_view', 'daily_view',
        'edit_timetables', 'new_calendar', 'import_', 'export_form']

    # Configuration
    config_name = '/agenda'
    config_group = 'content'

    # Fields
    timetables = Char_Field(datatype=Timetables, multiple=True,
        title=MSG(u'Timetables'))
    timetables_default = [
        (time( 7,0), time( 8,0)),
        (time( 8,0), time( 9,0)),
        (time( 9,0), time(10,0)),
        (time(10,0), time(11,0)),
        (time(11,0), time(12,0)),
        (time(12,0), time(13,0)),
        (time(13,0), time(14,0)),
        (time(14,0), time(15,0)),
        (time(15,0), time(16,0)),
        (time(16,0), time(17,0)),
        (time(17,0), time(18,0)),
        (time(18,0), time(19,0)),
        (time(19,0), time(20,0)),
        (time(20,0), time(21,0))]


    def init_resource(self, **kw):
        super(ConfigAgenda, self).init_resource(**kw)
        # Create default calendar
        kw = {'title': {'en': u'My events'}, 'color': '#AC81A1'}
        self.make_resource(None, Calendar, **kw)


    def get_timetables(self):
        """Build a list of timetables represented as tuples(start, end).
        Data are taken from metadata or from class value.

        Example of metadata:
          <timetables>(8,0),(10,0);(10,30),(12,0);(13,30),(17,30)</timetables>
        """
        timetables = self.get_value('timetables')
        if timetables:
            return timetables

        # From class value
        return self.timetables_default


    def get_document_types(self):
        return [Calendar, Event]


    #######################################################################
    # User Interface
    #######################################################################
    def to_ical(self, context):
        """Serialize as an ical file, generally named .ics
        """

        lines = ['BEGIN:VCALENDAR\n',
                'VERSION:2.0\n',
                'PRODID:-//itaapy.com/NONSGML ikaaro icalendar V1.0//EN\n']

        # Calendar components
        for event in self.search_resources(cls=Event):
            lines.append('BEGIN:VEVENT\n')
            for ikaaro_name, ics_name in ikaaro_to_ics:
                property = event.get_property(ikaaro_name)
                lang = property.get_parameter('lang')
                if lang:
                    property = Property(property.value, LANGUAGE=lang)
                    p_schema = {'LANGUAGE': String(multiple=False)}
                else:
                    p_schema = None
                datatype = event.get_field(ikaaro_name).datatype
                line = property_to_str(ics_name, property, datatype, p_schema)
                lines.append(line)

            lines.append('END:VEVENT\n')
        lines.append('END:VCALENDAR\n')

        return ''.join(lines)


    def parse_ical(self, data):
        """Parse iCal data to produce a sequence of tuples:

        name, value {param_name: param_value}

        Where all the elements ('name', 'value', 'param_name' and 'param_value')
        are byte strings.

        Only elements that are handled by Ikaaro are keeped
        """
        unfolded = unfold_lines(data)
        iterator = iter(unfolded)
        for line in iterator:
            parameters = {}
            name, line = read_name(line)
            # Read the parameters and the property value
            value, parameters = get_tokens(line)
            if name == 'BEGIN' and value not in ('VCALENDAR', 'VEVENT'):
                while get_tokens(read_name(iterator.next())[1])[0] != value:
                    pass
                continue
            else:
                yield name, value, parameters


    def load_state_from_ical_file(self, file):
        # Clear Calendar
        for event in self._get_names():
            self.del_resource(event)

        ical = iCalendar()
        ical.reset()
        ical._load_state_from_file(file)
        timezones = ical.get_components('VTIMEZONE')
        events = ical.get_components('VEVENT')

        i = 0
        for event in events:
            filename = str(i)
            properties = {}
            for name, value in event.get_property().items():
                if name in ics_to_ikaaro:
                    name = ics_to_ikaaro[name]
                    properties[name] = value.value
            properties['uid'] = event.uid
            self.make_resource(filename, Event, **properties)
            i += 1

    # Views
    monthly_view = MonthlyView
    weekly_view = WeeklyView
    daily_view = DailyView
    new_event = Calendar_NewEvent
    edit_timetables = TimetablesForm
    export = Calendar_Export
    import_ = Calendar_Import
    export_form = Calendar_ExportForm
    calendars = Calendars_View
    new_calendar = NewResource_Local(title=MSG(u'Add calendar'))
