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
from datetime import datetime, time

# Import from itools
from itools.core import merge_dicts
from itools.csv import Property, property_to_str
from itools.csv.table import get_tokens, read_name, unfold_lines
from itools.datatypes import DataType, Date, DateTime, Integer, String
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.file_views import File_View
from ikaaro.folder import Folder
from calendar_views import Calendar_Import, Calendar_Export
from calendar_views import MonthlyView, TimetablesForm, WeeklyView, DailyView
from event import Event


ikaaro_to_ics = [
    ('dtstart', 'DTSTART'),
    ('dtend', 'DTEND'),
    ('status', 'STATUS'),
    ('title', 'SUMMARY'),
    ('description', 'DESCRIPTION'),
    ('location', 'LOCATION'),
    ('mtime', 'UID')]

handled_ics_properties = tuple([y for x, y in ikaaro_to_ics])

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
            timetables.append((time(start[0], start[1]), time(end[0], end[1])))
        return timetables


    def to_ical(self):
        """Serialize as an ical file, generally named .ics
        """

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

    @classmethod
    def get_property_datatype(cls, name, default=String):
        if name.lower() in ('dtstart', 'dtend', 'ts'):
            return DateTime(multiple=False)
        if name in ('SEQUENCE', ):
            return Integer
        return Folder.get_property_datatype(name, default=default)


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

        # Read input file
        data = file.read()
        lines = []
        for name, value, parameters in self.parse_ical(data):
            # Timestamp (ts), Schema, or Something else
            datatype = self.get_property_datatype(name)
            value = datatype.decode(value)
            property = Property(value, **parameters)
            # Append
            lines.append((name, property))

        # Read first line
        first = lines[0]
        if (first[0] != 'BEGIN' or first[1].value != 'VCALENDAR'
            or first[1].parameters):
            raise ValueError, 'icalendar must begin with BEGIN:VCALENDAR'

        # Read last line
        last = lines[-1]
        if (last[0] != 'END' or last[1].value != 'VCALENDAR'
            or last[1].parameters):
            raise ValueError, 'icalendar must end with END:VCALENDAR'

        lines = lines[1:-1]


        ###################################################################
        # Skip properties
        # TODO Currently tables are not able to handler global properties,
        # we must implement this feature to be able to load from ical files.
        n_line = 0
        for name, value in lines:
            if name == 'BEGIN':
                break
            elif name == 'END':
                break
            n_line += 1

        lines = lines[n_line:]

        ###################################################################
        # Read components
        c_type = None
        c_inner_type = None
        uid = None
        id = 0
        uids = {}

        iterator = iter(lines)
        for prop_name, property in iterator:
            if prop_name in ('PRODID', 'VERSION'):
                raise ValueError, 'PRODID and VERSION must appear before '\
                                  'any component'
            if prop_name == 'BEGIN':
                if c_type is None:
                    c_type = property.value
                    c_properties = {}
                    c_inner_components = []
                else:
                    # Inner component like DAYLIGHT or STANDARD
                    c_inner_type = property.value
                    c_inner_properties = {}
                continue

            if prop_name == 'END':
                value = property.value
                if value == c_type:
                    if uid is None:
                        raise ValueError, 'UID is not present'

                    filename = str(id)
                    event = self.get_resource(filename, soft=True)
                    c_properties['type'] = Property(c_type)
                    c_properties['UID'] = Property(uid)
                    c_properties['ts'] = Property(str(datetime.now()))
                    # Add ids of inner components
                    if c_inner_components:
                        c_inner_components = [Property(str(x))
                                              for x in c_inner_components]
                        c_properties['inner'] = c_inner_components
                    # Convert properties name from ics to ikaaro format
                    for ikaaro_name, ics_name in ikaaro_to_ics:
                        if c_properties.has_key(ics_name):
                            c_properties[ikaaro_name] = c_properties[ics_name]
                            del c_properties[ics_name]
                    if event:
                        for name, value in c_properties.items():
                            event.set_property(name, value)
                    else:
                        self.make_resource(filename, Event, **c_properties)
                    if uid in uids:
                        n = uids[uid] + 1
                        uids[uid] = n
                    else:
                        n = 0
                        uids[uid] = 0

                    # Next
                    c_type = None
                    uid = None
                    if n == 0:
                        id = id + 1

                # Inner component
                elif value == c_inner_type:
                    filename = str(id)
                    event = self.get_resource(filename, soft=True)
                    c_inner_properties['type'] = Property(c_inner_type)
                    c_inner_properties['ts'] = Property(datetime.now())
                    c_inner_components.append(id)
                    if event:
                        for name, value in c_properties.items():
                            event.set_property(name, value)
                    else:
                        self.make_resource(filename, Event, **c_properties)
                    # Next
                    c_inner_type = None
                    id = id + 1
                else:
                    raise ValueError, 'Component %s found, %s expected' \
                                      % (value, c_inner_type)
            elif prop_name in handled_ics_properties:
                c_inner_type
                datatype = self.get_property_datatype(prop_name)
                if c_inner_type is None:
                    if prop_name in ('UID', 'TZID'):
                        uid = property.value
                    else:
                        if prop_name in ('SUMMARY', 'DESCRIPTION'):
                            lang = {'lang': 'en'}
                            if property.parameters:
                                property.parameters.update(lang)
                            else:
                                property.parameters = lang
                        if getattr(datatype, 'multiple', False) is True:
                            value = c_properties.setdefault(prop_name, [])
                            value.append(property.value)
                        else:
                            # Check the property has not yet being found
                            if prop_name in c_properties:
                                raise ValueError, \
                                    "property '%s' can occur only once" % name
                            # Set the property
                            c_properties[prop_name] = property
                else:
                    # Inner component properties
                    if getattr(datatype, 'multiple', False) is True:
                        value = c_inner_properties.setdefault(prop_name, [])
                        value.append(property.value)
                    else:
                        # Check the property has not yet being found
                        if prop_name in c_inner_properties:
                            msg = ('the property %s can be assigned only one'
                                   ' value' % prop_name)
                            raise ValueError, msg
                        # Set the property
                        c_inner_properties[prop_name] = property.value
            #else: Ignorated components


    # Views
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    daily_view = DailyView()
    edit_timetables = TimetablesForm()
    export = Calendar_Export()
    import_ = Calendar_Import()
    export_form = File_View(title=MSG(u'Export'),
                            template='/ui/calendar/export_form.xml')



###########################################################################
# XXX Upgrade code, to remove in 0.71
###########################################################################
from ikaaro.table import Table


class CalendarTable(Table):

    class_id = 'calendarTable'
    class_version = '20100602'


    def update_20100602(self):
        parent = self.parent

        # Remove myself
        handler = self.handler.clone()
        parent.del_resource(self.name)

        # New calendar
        parent.make_resource(self.name, Calendar)
        # TODO Import the old data from 'handler'
