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
from datetime import datetime, date, time, timedelta
from operator import itemgetter

# Import from itools
from itools.uri import encode_query
from itools.datatypes import DataType, Date, Enumerate, Integer
from itools.datatypes import is_datatype
from itools.gettext import MSG
from itools.ical import icalendar, icalendarTable
from itools.ical import Record, Time
from itools.stl import stl
from itools.web import FormError
from itools.web import MSG_MISSING_OR_INVALID

# Import from ikaaro
from calendar_views import CalendarUpload, DownloadView, EditEventForm
from calendar_views import MonthlyView, TimetablesForm, WeeklyView
from calendar_views import get_current_date
from folder import Folder
from messages import MSG_CHANGES_SAVED
from registry import register_object_class
from table import Multiple, Table
from text import Text


description = u'Schedule your time with calendar files.'


def build_timetables(start_time, end_time, interval):
    """Build a list of timetables represented as tuples(start, end).
    Interval is given by minutes.
    """
    start =  datetime(2000, 1, 1)
    if start_time:
        start = datetime.combine(start.date(), start_time)
    end =  datetime(2000, 1, 1, 23, 59)
    if end_time:
        end = datetime.combine(start.date(), end_time)

    timetables, tt_start = [], start
    while tt_start < end:
        tt_end = tt_start + timedelta(minutes=interval)
        timetables.append((tt_start.time(), tt_end.time()))
        tt_start = tt_end
    return timetables



class Timetables(DataType):
    """Timetables are tuples of time objects (start, end) used by cms.ical.

    Example with 3 timetables as saved into metadata:
        (8,0),(10,0);(10,0),(12,0);(15,30),(17,30)

    Decoded value are:
        [(time(8,0), time(10,0)), (time(10,0), time(12, 0)),
         (time(15,30), time(17, 30))]
    """

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



class CalendarView(object):

    # Start 07:00, End 21:00, Interval 30min
    class_cal_range = (time(7,0), time(21,0), 30)
    class_cal_fields = ('SUMMARY', 'DTSTART', 'DTEND')


    @classmethod
    def get_cal_range(cls):
        return cls.class_cal_range


    @classmethod
    def get_cal_fields(cls):
        return cls.class_cal_fields


    # Get one line with times of timetables for daily_view
    def get_header_timetables(self, timetables, delta=45):
        current_date = date.today()
        timetable = timetables[0]
        last_start = datetime.combine(current_date, timetable[0])

        ns_timetables = []
        # Add first timetable start time
        ns_timetable =  {'start': last_start.strftime('%H:%M')}
        ns_timetables.append(ns_timetable)

        # Add next ones if delta time > delta minutes
        for timetable in timetables[1:]:
            tt_start = timetable[0]
            tt_start = datetime.combine(current_date, tt_start)
            if tt_start - last_start > timedelta(minutes=delta):
                ns_timetable =  {'start': tt_start.strftime('%H:%M')}
                ns_timetables.append(ns_timetable)
                last_start = tt_start
            else:
                ns_timetables.append({'start': None})

        return ns_timetables


    # Get one line with header and empty cases with only '+' for daily_view
    def get_header_columns(self, calendar_name, args, timetables, cal_fields,
                           new_class='add_event', new_value='+'):
        ns_columns = []
        for start, end in timetables:
            tmp_args = dict(args)
            start = Time.encode(start)
            tmp_args['start_time'] = start
            end = Time.encode(end)
            tmp_args['end_time'] = end
            tmp_args['id'] = calendar_name
            new_url = ';edit_event?%s' % encode_query(tmp_args)
            column =  {'class': None,
                       'colspan': 1,
                       'rowspan': 1,
                       'DTSTART': start,
                       'DTEND': end,
                       'new_url': new_url,
                       'new_class': new_class,
                       'new_value': new_value}
            # Fields in template but not shown
            for field in cal_fields:
                if field not in column:
                    column[field] = None
            ns_columns.append(column)
        return ns_columns



class CalendarAwareView(CalendarView):

    edit_event__access__ = 'is_allowed_to_edit'
    def edit_event(self, context):
        id = context.get_form_value('id')
        if '/' in id:
            name, id = id.split('/', 1)
        else:
            name = context.get_form_value('resource')
        if name and self.has_resource(name):
            object = self.get_resource(name)
            return object.edit_event(context)
        message = MSG(u'Resource not found.')
        return context.come_back(message)


    # Get namespace for a resource's lines into daily_view
    def get_ns_calendar(self, calendar, c_date, cal_fields, shown_fields,
                        timetables, method='daily_view', show_conflicts=False):
        calendar_name = calendar.name
        args = {'date': Date.encode(c_date), 'method': method}

        ns_calendar = {}
        ns_calendar['name'] = calendar.get_title()

        # Get a dict for each event, compute colspan
        handler = calendar.handler
        events_by_index = {}
        for event in handler.search_events_in_date(c_date):
            event_namespace = {}
            for field in shown_fields:
                event_namespace[field] = event.get_property(field).value
            event_start = event.get_property('DTSTART').value
            event_end = event.get_property('DTEND').value
            # Compute start and end indexes
            tt_start = 0
            tt_end = len(timetables) - 1
            for tt_index, (start, end) in enumerate(timetables):
                start = datetime.combine(c_date, start)
                end = datetime.combine(c_date, end)
                if start <= event_start:
                    tt_start = tt_index
                if end >= event_end:
                    tt_end = tt_index
                    break
            event_namespace['tt_start'] = tt_start
            event_namespace['tt_end'] = tt_end
            uid = getattr(event, 'id', getattr(event, 'uid', None))
            if uid:
                uid = '%s/%s' % (calendar_name, uid)
            event_namespace['UID'] = uid
            event_namespace['colspan'] = tt_end - tt_start + 1
            if not tt_start in events_by_index:
                events_by_index[tt_start] = []
            events_by_index[tt_start].append(event_namespace)

        # Organize events in rows
        # If a row index is busy, start a new row
        rows = []
        for index in range(len(timetables)):
            events = events_by_index.get(index)
            if events is None:
                continue
            # Sort events by tt_end to reduce fragmentation
            # Longer events go on lines of their own
            events.sort(key=itemgetter('tt_end'))
            for row_index, event in enumerate(events):
                if not rows or len(rows) <= row_index:
                    rows.append({'events': []})
                current_events = rows[row_index]['events']
                if (current_events
                        and current_events[-1]['tt_end'] >= index):
                    # Overlapping, move on a line of its own
                    rows.append({'events': [event]})
                else:
                    # Enough free space, extend
                    current_events.append(event)

        # Get the list of conflicting events if activated
        if show_conflicts:
            conflicts_list = set()
            conflicts = handler.get_conflicts(c_date)
            if conflicts:
                for uids in conflicts:
                    uids = ['%s/%s' % (calendar_name, uid) for uid in uids]
                    conflicts_list.update(uids)

        # Organize columns
        rows_namespace = []
        for row in rows:
            row_namespace = {}
            columns_namespace = []
            events = row['events']
            event = events.pop(0)
            colspan = 0
            for tt_index, (start, end) in enumerate(timetables):
                if colspan > 0:
                    colspan = colspan - 1
                    continue
                tmp_args = dict(args)
                tmp_args['start_time'] = Time.encode(start)
                tmp_args['end_time'] = Time.encode(end)
                new_url = ';edit_event?%s' % encode_query(tmp_args)
                # Init column
                column =  {'class': None,
                           'colspan': 1,
                           'rowspan': 1,
                           'evt_url': None,
                           'evt_value': '>>',
                           'new_url': new_url,
                           'new_class': 'add_event',
                           'new_value': '+'}
                # Add event
                if event and tt_index == event['tt_start']:
                    uid = event['UID']
                    tmp_args = dict(args)
                    tmp_args['id'] = uid
                    go_url = ';edit_event?%s' % encode_query(tmp_args)
                    if show_conflicts and uid in conflicts_list:
                        css_class = 'cal_conflict'
                    else:
                        css_class = 'cal_busy'
                    column['class'] = css_class
                    column['colspan'] = event['colspan']
                    column['evt_url'] = go_url
                    column['new_url'] = None
                    column['evt_value'] = '>>'
                    # Fields to show
                    for field in shown_fields:
                        value = event[field]
                        if isinstance(value, datetime):
                            value = value.strftime('%H:%M')
                        column[field] = value
                    # Set colspan
                    colspan = event['colspan'] - 1
                    # Delete added event
                    event = None
                    if events != []:
                        event = events.pop(0)
                # Fields in template but not shown
                for field in cal_fields:
                    if field not in column:
                        column[field] = None
                columns_namespace.append(column)
                row_namespace['columns'] = columns_namespace
            rows_namespace.append(row_namespace)

        # Add rows_namespace to namespace
        ns_calendar['rows'] = rows_namespace

        # Add one line with header and empty cases with only '+'
        header_columns = self.get_header_columns(calendar_name, args,
                                                 timetables, cal_fields)
        ns_calendar['header_columns'] = header_columns

        # Add url to calendar keeping args
        ns_calendar['url'] = ';monthly_view?%s' % args
        ns_calendar['rowspan'] = len(rows) + 1

        return ns_calendar


    daily_view__access__ = 'is_allowed_to_edit'
    daily_view__label__ = u'Daily View'
    def daily_view(self, context):
        method = context.get_cookie('method')
        if method != 'daily_view':
            context.set_cookie('method', 'daily_view')

        # Current date
        selected_date = context.get_form_value('date')
        c_date = get_current_date(selected_date)
        selected_date = Date.encode(c_date)

        # Get fields and fields to show
        cal_fields = self.get_cal_fields()
        shown_fields = self.get_weekly_shown()

        namespace = {}
        # Add date selector
        namespace['date'] = selected_date
        namespace['firstday'] = self.get_first_day()
        namespace['link_on_summary'] = True

        # Add a header line with start time of each timetable
        start, end, interval = self.get_cal_range()
        timetables = build_timetables(start, end, interval)
        namespace['header_timetables'] = self.get_header_timetables(timetables)

        # For each found calendar
        ns_calendars = []
        for calendar in self.get_calendars():
            ns_calendar = self.get_ns_calendar(calendar, c_date, cal_fields,
                                               shown_fields, timetables)
            ns_calendars.append(ns_calendar)
        namespace['calendars'] = ns_calendars

        handler = self.get_resource('/ui/ical/daily_view.xml')
        return stl(handler, namespace)



###########################################################################
# Model
###########################################################################
class CalendarBase():

    class_title = MSG(u'Calendar')
    class_description = MSG(description)
    class_icon16 = 'icons/16x16/icalendar.png'
    class_icon48 = 'icons/48x48/icalendar.png'
    class_views = ['monthly_view', 'weekly_view', 'download', 'upload',
                   'edit_timetables', 'edit_metadata']


    timetables = [((7,0),(8,0)), ((8,0),(9,0)), ((9,0),(10,0)),
                  ((10,0),(11,0)), ((11,0),(12,0)), ((12,0),(13,0)),
                  ((13,0),(14,0)), ((14,0),(15,0)), ((15,0),(16,0)),
                  ((16,0),(17,0)), ((17,0),(18,0)), ((18,0),(19,0)),
                  ((19,0),(20,0)), ((20,0),(21,0))]


    def get_calendars(self):
        return [self]


    def get_action_url(self, **kw):
        url = ';edit_event'
        params = []
        if 'day' in kw:
            params.append('date=%s' % Date.encode(kw['day']))
        if 'id' in kw:
            params.append('id=%s' % kw['id'])
        if params != []:
            url = '%s?%s' % (url, '&'.join(params))
        return url


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
    download = DownloadView()
    upload = CalendarUpload()
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    edit_timetables = TimetablesForm()
    edit_event = EditEventForm()



class CalendarTable(Table, CalendarBase):

    class_id = 'calendarTable'
    class_version = '20071216'
    class_handler = icalendarTable
    record_class = Record


    def get_record(self, id):
        id = int(id)
        return self.handler.get_record(id)


    def add_record(self, type, properties):
        properties['type'] = type
        return self.handler.add_record(properties)


    def update_record(self, id, properties):
        id = int(id)
        self.handler.update_record(id, **properties)


    def _remove_event(self, uid):
        self.handler.del_record(int(uid))


    @classmethod
    def get_metadata_schema(cls):
        schema = Table.get_metadata_schema()
        schema['timetables'] = Timetables
        return schema


    edit_record__access__ = 'is_allowed_to_edit'
    def edit_record(self, context):
        # check form
        check_fields = {}
        for name, kk in self.get_fields():
            datatype = self.handler.get_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[name] = datatype

        try:
            form = context.check_form_input(check_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID, keep=True)

        # Get the record
        id = context.get_form_value('id', type=Integer)
        record = {}
        for name, title in self.get_fields():
            datatype = self.handler.get_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = context.get_form_values(name)
                else: # textarea -> string
                    values = context.get_form_value(name)
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[value]
            record[name] = value

        self.handler.update_record(id, **record)
        goto = context.uri.resolve2('../;edit_record_form')
        return context.come_back(MSG_CHANGES_SAVED, goto=goto, keep=['id'])



class Calendar(Text, CalendarBase):

    class_id = 'text/calendar'
    class_version = '20071216'
    class_handler = icalendar


    def get_record(self, id):
        return self.handler.get_record(id)


    def add_record(self, type, properties):
        return self.handler.add_component(type, **properties)


    def update_record(self, id, properties):
        self.handler.update_component(id, **properties)


    def _remove_event(self, uid):
        self.handler.remove(uid)


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
        if not types:
            types = (Calendar, CalendarTable)
        if isinstance(self, Folder):
            calendars = list(self.search_objects(object_class=types))
            return calendars
        return [self]


    #######################################################################
    # Views
    #######################################################################
    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    edit_timetables = TimetablesForm()
    edit_event = EditEventForm()

    download = None
    upload = None



###########################################################################
# Register
###########################################################################
register_object_class(CalendarTable)
register_object_class(Calendar)
