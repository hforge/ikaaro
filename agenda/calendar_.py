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
from itools.csv.table import get_tokens, read_name, unfold_lines
from itools.datatypes import DataType, Integer, String
from itools.gettext import MSG
from itools.ical import iCalendar

# Import from ikaaro
from ikaaro.folder import Folder
from calendar_views import Calendar_Export, Calendar_ExportForm
from calendar_views import Calendar_Import
from calendar_views import MonthlyView, TimetablesForm, WeeklyView, DailyView
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

    class_id = 'calendar'
    class_title = MSG(u'Calendar')
    class_description = MSG(u'Schedule your time with calendar files.')
    class_icon16 = 'icons/16x16/calendar.png'
    class_icon48 = 'icons/48x48/calendar.png'
    class_views = ['monthly_view', 'weekly_view', 'daily_view',
                   'edit_timetables', 'import_', 'export_form']

    timetables = [((7,0),(8,0)), ((8,0),(9,0)), ((9,0),(10,0)),
                  ((10,0),(11,0)), ((11,0),(12,0)), ((12,0),(13,0)),
                  ((13,0),(14,0)), ((14,0),(15,0)), ((15,0),(16,0)),
                  ((16,0),(17,0)), ((17,0),(18,0)), ((18,0),(19,0)),
                  ((19,0),(20,0)), ((20,0),(21,0))]

    colors = ['#AC81A1', '#719C71', '#C1617C', '#A0A5B5', '#A59580']


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
    # Test if user in context is the organizer of a given event (or is admin)
    def is_organizer_or_admin(self, context, event):
        if self.get_access_control().is_admin(context.user, self):
            return True
        if event:
            organizer = event.get_owner()
            username = str(context.user.name)
            return organizer and username == organizer
        ac = self.parent.get_access_control()
        return ac.is_allowed_to_edit(context.user, self.parent)


    def get_timetables(self):
        """Build a list of timetables represented as tuples(start, end).
        Data are taken from metadata or from class value.

        Example of metadata:
          <timetables>(8,0),(10,0);(10,30),(12,0);(13,30),(17,30)</timetables>
        """
        timetables = self.get_property('timetables')
        if timetables:
            return timetables

        # From class value
        timetables = []
        for index, (start, end) in enumerate(self.timetables):
            timetables.append((time(start[0], start[1]), time(end[0], end[1])))
        return timetables


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
                datatype = event.get_property_datatype(ikaaro_name)
                property = event.metadata.get_property(ikaaro_name)
                if property:
                    lang = property.get_parameter('lang')
                    if lang:
                        property = Property(property.value, LANGUAGE=lang)
                    p_schema = {'LANGUAGE': String(multiple=False)}
                # Assume default value
                else:
                    value = datatype.get_default()
                    property = Property(value)
                    p_schema = None
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
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    daily_view = DailyView()
    edit_timetables = TimetablesForm()
    export = Calendar_Export()
    import_ = Calendar_Import()
    export_form = Calendar_ExportForm()



###########################################################################
# XXX Upgrade code, to remove in 0.71
###########################################################################
from itools.csv import Table as TableFile
from itools.ical.datatypes import record_properties
from ikaaro.table import Table


class icalendarTable(TableFile):
    """The old handler class for table base calendars.
    """

    record_properties = merge_dicts(
        record_properties,
        type=String(indexed=True),
        inner=Integer(multiple=True))



class CalendarTable(Table):

    class_id = 'calendarTable'
    class_version = '20100602'
    class_handler = icalendarTable


    def update_20100602(self):
        from ikaaro.metadata import is_multilingual

        # Remove myself
        handler = self.handler.clone()
        parent = self.parent
        parent.del_resource(self.name, ref_action='force')

        # New calendar
        self = parent.make_resource(self.name, Calendar)
        # Import old data
        lang = parent.get_site_root().get_default_language()
        for i, event in enumerate(handler.records):
            # deleted record or not an event
            if event is None or event['type'].value != 'VEVENT':
                continue
            filename = str(i)
            properties = {}
            for name, property in event.items():
                if name in ics_to_ikaaro:
                    name = ics_to_ikaaro[name]
                    datatype = Event.get_property_datatype(name)
                    if is_multilingual(datatype):
                        property = Property(property.value, lang=lang)
                    properties[name] = property
            properties['uid'] = event['UID']
            self.make_resource(filename, Event, **properties)
