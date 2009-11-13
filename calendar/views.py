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
from calendar import monthrange, isleap
from cStringIO import StringIO
from datetime import date, datetime, time, timedelta
from operator import itemgetter

# Import from itools
from itools.core import thingy_property, thingy_lazy_property
from itools.datatypes import Date, Enumerate, Integer
from itools.gettext import MSG
from itools.http import get_context
from itools.ical import Time
from itools.stl import stl
from itools.uri import get_reference
from itools.web import BaseView, STLForm, STLView, INFO, ERROR
from itools.web import file_field
from itools.xapian import AndQuery, PhraseQuery, RangeQuery

# Import from ikaaro
from grid import get_grid_data
from ikaaro.fields import DateField


resolution = timedelta.resolution

months = {
    1: MSG(u'January'),
    2: MSG(u'February'),
    3: MSG(u'March'),
    4: MSG(u'April'),
    5: MSG(u'May'),
    6: MSG(u'June'),
    7: MSG(u'July'),
    8: MSG(u'August'),
    9: MSG(u'September'),
    10: MSG(u'October'),
    11: MSG(u'November'),
    12: MSG(u'December')}

days = {
    0: MSG(u'Monday'),
    1: MSG(u'Tuesday'),
    2: MSG(u'Wednesday'),
    3: MSG(u'Thursday'),
    4: MSG(u'Friday'),
    5: MSG(u'Saturday'),
    6: MSG(u'Sunday')}



class Status(Enumerate):

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class TimetablesForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Timetables')
    template = '/ui/calendar/edit_timetables.xml'
    styles = ['/ui/calendar/style.css']


    def get_namespace(self, resource, context):
        # Show current timetables only if previously set in metadata
        if resource.has_property('timetables'):
            timetables = resource.get_property('timetables')
            timetables_ns = [
                {'index': index,
                 'startname': '%s_start' % index,
                 'endname': '%s_end' % index,
                 'start': Time.encode(start),
                 'end': Time.encode(end)}
                for index, (start, end) in enumerate(timetables) ]
        else:
            timetables_ns = []

        # Ok
        return {'timetables': timetables_ns}


    action_add_schema = {'new_start': Time, 'new_end': Time}
    def action_add(self, resource, context, form):
        # Check start time is before end time
        start = form['new_start']
        end = form['new_end']
        if start >= end:
            message = ERROR(u'Start time must be earlier than end time.')
            context.message = message
            return

        # Check the given range is not defined yet
        timetables = resource.get_property('timetables')
        if (start, end) in timetables:
            context.message = ERROR(u'The given range is already defined.')
            return

        # Add new range
        timetables = list(timetables)
        timetables.append((start, end))
        timetables.sort()
        resource.set_property('timetables', tuple(timetables))
        # Ok
        context.message = INFO(u'Timetables updated successfully.')


    action_remove_schema = {'ids': Integer(multiple=True)}
    def action_remove(self, resource, context, form):
        ids = form['ids']
        if len(ids) == 0:
            context.message = ERROR(u'Nothing to remove.')
            return

        # New timetables
        timetables = resource.get_property('timetables')
        timetables = [
            timetable for index, timetable in enumerate(timetables)
            if index not in ids ]
        resource.set_property('timetables', tuple(timetables))
        # Ok
        context.message = INFO(u'Timetable(s) removed successfully.')


    def action_update(self, resource, context, form):
        timetables = resource.get_property('timetables')
        if len(timetables) == 0:
            context.message = ERROR(u'Nothing to change.')
            return

        # Update timetable or just set index to next index
        new_timetables = []
        for index in range(len(timetables)):
            try:
                start = context.get_form_value('%s_start' % index, type=Time)
                end = context.get_form_value('%s_end' % index, type=Time)
            except:
                context.message = ERROR(u'Wrong time selection (HH:MM).')
                return

            if start >= end:
                message = ERROR(u'Start time must be earlier than end time.')
                context.message = message
                return

            new_timetables.append((start, end))

        new_timetables.sort()
        resource.set_property('timetables', tuple(new_timetables))
        # Ok
        context.message = INFO(u'Timetables updated successfully.')



class CalendarView(STLView):

    styles = ['/ui/calendar/style.css']
    add_icon = '/ui/icons/16x16/add.png'
    ndays = 7
    with_new_url = True

    # default viewed fields on monthly_view
    default_viewed_fields = ('dtstart', 'dtend', 'SUMMARY', 'STATUS')

    date = DateField(source='query')


    # Returns 0 if Sunday is the first day of the week, else 1.
    # For now it has to be overridden to return anything else than 1.
    first_day = 1


    @thingy_lazy_property
    def method(self):
        method = self._method

        # Set cookie
        context = self.context
        if context.get_cookie('method') != method:
            context.set_cookie('method', method)

        # Ok
        return method


    @thingy_lazy_property
    def c_date(self):
        context = self.context

        # Current date
        c_date = self.date.value
        if not c_date:
            c_date = context.get_cookie('selected_date')
            if c_date:
                c_date = Date.decode(c_date)
            else:
                c_date = date.today()

        # Save selected date
        context.set_cookie('selected_date', c_date)
        return c_date


    @thingy_property
    def week_number(self):
        """datetime.strftime('%U') gives week number, starting week by sunday
           datetime.strftime('%W') gives week number, starting week by monday
           This week number is calculated as "Week 1" begins on the first
           sunday/monday of the year. Its range is [0, 53].

        We adjust week numbers to fit rules which are used by French people.
        XXX Check for other countries.
        """
        c_date = self.c_date
        if self.first_day == 1:
            format = '%W'
        else:
            format = '%U'
        week_number = int(c_date.strftime(format))
        # Get day of 1st January, if < friday and != monday then number++
        day, kk = monthrange(c_date.year, 1)
        if day in (1, 2, 3):
            week_number = week_number + 1
        return week_number


    def search(self, query=None, **kw):
        if query is None:
            query = [ PhraseQuery(name, value) for name, value in kw.items() ]
        else:
            query = [query]

        # Search only events
        query.append(PhraseQuery('format', 'event'))
        query = AndQuery(*query)

        # Search
        return get_context().search(query)


    def search_events_in_range(self, start, end, **kw):
        query = [ PhraseQuery(name, value) for name, value in kw.items() ]
        query = AndQuery(
            RangeQuery('dtstart', None, end),
            RangeQuery('dtend', start, None),
            *query)
        return self.search(query)


    def search_events_in_date(self, date, **kw):
        """Return a list of Component objects of type 'VEVENT' matching the
        given date and sorted if requested.
        """
        dtstart = datetime(date.year, date.month, date.day)
        dtend = dtstart + timedelta(days=1) - resolution
        return self.search_events_in_range(dtstart, dtend, **kw)


    def get_events_to_display(self, start, end):
        events = self.search_events_in_range(start, end)
        return events.get_documents(sort_by='dtstart')


    def get_action_url(self, **kw):
        if 'day' in kw:
            url = ';new_resource?type=event&dtstart=%s&dtend=%s'
            date = Date.encode(kw['day'])
            return url % (date, date)
        if 'id' in kw:
            return '%s/;edit' % kw['id']

        return None


    def next_year(self):
        c_date = self.c_date
        year, month, day = c_date.year, c_date.month, c_date.day
        if month == 2 and day == 29:
            day = 28

        tmp_date = date(year + 1, month, day)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def current_year(self):
        return self.c_date.year


    def previous_year(self):
        c_date = self.c_date
        year, month, day = c_date.year, c_date.month, c_date.day
        if month == 2 and day == 29:
            day = 28

        tmp_date = date(year - 1, month, day)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def next_month(self):
        c_date = self.c_date
        kk, delta = monthrange(c_date.year, c_date.month)
        tmp_date = c_date + timedelta(delta)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def current_month(self):
        return months[self.c_date.month].gettext()


    def previous_month(self):
        c_date = self.c_date
        if c_date.month != 1:
            kk, delta = monthrange(c_date.year, c_date.month - 1)
        else:
            delta = 31
        tmp_date = c_date - timedelta(delta)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def next_week(self):
        tmp_date = self.c_date + timedelta(7)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def current_week(self):
        return MSG(u'Week {n}').gettext(n=self.week_number)


    def previous_week(self):
        tmp_date = self.c_date - timedelta(7)
        return ";%s?date=%s" % (self.method, Date.encode(tmp_date))


    def today(self):
        today = date.today()
        return ";%s?date=%s" % (self.method, Date.encode(today))


    @thingy_lazy_property
    def start(self):
        """Calculate start of previous week
        """
        # 0 = Monday, ..., 6 = Sunday
        c_date = self.c_date
        weekday = c_date.weekday()
        start = c_date - timedelta(7 + weekday)
        if self.first_day == 0:
            return start - timedelta(1)
        return start


    # Get days of week based on get_first_day's result for start
    def days_of_week(self, num=False, selected=None):
        """
          start : start date of the week
          num : True if we want to get number of the day too
          selected : selected date
        """
        resource = get_context().resource
        current_date = self.start
        ns_days = []
        for index in range(self.ndays):
            ns =  {}
            ns['name'] = days[current_date.weekday()].gettext()
            if num:
                ns['nday'] = current_date.day
            else:
                ns['nday'] = None
            if selected:
                ns['selected'] = (selected == current_date)
            else:
                ns['selected'] = None
            ns_days.append(ns)
            current_date = current_date + timedelta(1)
        return ns_days


    ######################################################################
    # Public API
    ######################################################################
    def events_to_namespace(self, events, day, grid=False,
                            show_conflicts=False):
        """Build namespace for events occuring on current day.
        Update events, removing past ones.

        Events is a list of events where each one follows:
          (resource_name, dtstart, event)
          'event' object must have a methods:
              - get_ns_event
        """
        handler = self.resource.handler
        context = self.context

        ns_events = []
        index = 0
        while index < len(events):
            event = events[index]
            e_dtstart = event.get_value('dtstart').date()
            e_dtend = event.get_value('dtend').date()
            # Current event occurs on current date
            # event begins during current tt
            starts_on = e_dtstart == day
            # event ends during current tt
            ends_on = e_dtend == day
            # event begins before and ends after
            out_on = (e_dtstart < day and e_dtend > day)

            if starts_on or ends_on or out_on:
                cal_index = 0
                conflicts_list = set()
                if show_conflicts:
                    conflicts = handler.get_conflicts(e_dtstart, e_dtend)
                    if conflicts:
                        for uids in conflicts:
                            conflicts_list.update(uids)
                ns_event = event.get_ns_event(day,
                                              conflicts_list=conflicts_list,
                                              grid=grid, starts_on=starts_on,
                                              ends_on=ends_on, out_on=out_on)
                ns_event['url'] = self.get_action_url(**ns_event)
                ns_event['cal'] = cal_index
                if 'resource' in ns_event.keys():
                    ns_event['resource']['color'] = cal_index
                else:
                    ns_event['resource'] = {'color': cal_index}
                ns_events.append(ns_event)
                # Current event end on current date
                if e_dtend == day:
                    events.remove(events[index])
                    if events == []:
                        break
                else:
                    index = index + 1
            # Current event occurs only later
            elif e_dtstart > day:
                break
            else:
                index = index + 1
        return ns_events, events



class MonthlyView(CalendarView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Month View')
    template = 'calendar/monthly_view.xml'
    monthly_template = 'calendar/monthly_template.xml'

    _method = 'monthly_view'


    def weeks(self):
        today_date = date.today()

        ###################################################################
        # Get a list of events to display on view
        if type(self.monthly_template) is str:
            template = self.context.get_template(self.monthly_template)
        else:
            template = self.monthly_template

        # Calculate last date to take in account as we display  5*7 = 35 days
        start = self.start
        end = start + timedelta(35)
        events = self.get_events_to_display(start, end)
        events = list(events)

        weeks = []
        day = start
        # 5 weeks
        for w in range(5):
            ns_week = {'days': [], 'month': u''}
            # 7 days a week
            for d in range(7):
                # day in timetable
                if d < self.ndays:
                    # Insert events
                    ns_events, events = self.events_to_namespace(events, day)
                    ns_week['days'].append(
                        {'nday': day.day,
                         'selected': (day == today_date),
                         'url': self.get_action_url(day=day),
                         'events': stl(template, {'events': ns_events})})
                    if day.day == 1:
                        month = months[day.month].gettext()
                        ns_week['month'] = month
                day = day + timedelta(1)
            weeks.append(ns_week)
        return weeks



class WeeklyView(CalendarView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Week View')
    template = 'calendar/weekly_view.xml'
    _method = 'weekly_view'


    timetables = [
        ((7,0), (8,0)), ((8,0), (9,0)), ((9,0), (10,0)), ((10,0), (11,0)),
        ((11,0), (12,0)), ((12,0), (13,0)), ((13,0), (14,0)), ((14,0),
        (15,0)), ((15,0), (16,0)), ((16,0), (17,0)), ((17,0), (18,0)),
        ((18,0), (19,0)), ((19,0), (20,0)), ((20,0), (21,0))]


    def get_weekly_templates(self):
        """Get weekly templates to display events with timetables, and full
        day events.
        """
        return None, None


    def get_timetables(self):
        """Build a list of timetables represented as tuples(start, end).
        Data are taken from metadata or from class value.

        Example of metadata:
          <timetables>(8,0),(10,0);(10,30),(12,0);(13,30),(17,30)</timetables>
        """
        # From class value
        timetables = []
        for index, (start, end) in enumerate(self.timetables):
            timetables.append((time(start[0], start[1]), time(end[0], end[1])))
        return timetables


    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self):
        """Build namespace to give as grid to gridlayout factory.
        """
        ns_timetables = []
        for start, end in self.get_timetables():
            for value in (start, end):
                value = Time.encode(value)
                if value not in ns_timetables:
                    ns_timetables.append(value)
        return ns_timetables


    def get_grid_events(self, headers=None, step=timedelta(1)):
        """Build namespace to give as data to gridlayout factory.
        """
        start_date = self.start
        ndays = self.ndays

        # Get events by day
        ns_days = []
        current_date = start_date

        if headers is None:
            headers = [None] * ndays

        # For each found calendar (or self), get events
        # Get a list of events to display on view
        end = start_date + timedelta(days=ndays)
        events = self.get_events_to_display(start_date, end)
        events = list(events)

        for header in headers:
            ns_day = {}
            # Add header if given
            ns_day['header'] = header
            # Insert events
            ns_events, events = self.events_to_namespace(events, current_date,
                                                         grid=True)
            ns_day['events'] = ns_events
            ns_days.append(ns_day)
            current_date = current_date + step

        return ns_days


    @thingy_lazy_property
    def start(self):
        """Calculate start of current week
        """
        # 0 = Monday, ..., 6 = Sunday
        c_date = self.c_date
        weekday = c_date.weekday()
        start = c_date - timedelta(weekday)
        if self.first_day == 0:
            return start - timedelta(1)
        return start


    def timetable_data(self):
        # Get the events
        days_of_week = self.days_of_week(True, self.c_date)
        ns_headers = [ '%s %s' % (x['name'], x['nday']) for x in days_of_week ]
        events = self.get_grid_events(headers=ns_headers)

        # Calculate timetables and events occurring for current week
        timetables = self.get_timetables_grid_ns()

        # Fill data with grid (timetables) and data (events for each day)
        templates = self.get_weekly_templates()
        return get_grid_data(events, timetables, self.start, templates,
                             self.with_new_url)



class DailyView(CalendarView):

    access = 'is_allowed_to_view'
    view_title = MSG(u'Day View')
    template = 'calendar/daily_view.xml'
    _method = 'daily_view'


    # Start 07:00, End 21:00, Interval 30min
    class_cal_range = (time(7,0), time(21,0), 30)
    class_cal_fields = ('SUMMARY', 'DTSTART', 'DTEND')


    def get_cal_range(self):
        return self.class_cal_range


    # Get namespace for a resource's lines into daily_view
    def get_ns_calendar(self, c_date, timetables, show_conflicts=False):
        cal_fields = self.class_cal_fields
        resource = self.resource
        calendar_name = str(resource.get_name())

        # Get a dict for each event, compute colspan
        handler = resource.handler
        events_by_index = {}
        for event in self.search_events_in_date(c_date).get_documents():
            event_start = event.dtstart
            event_end = event.dtend
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
            uid = event.abspath
            events_by_index.setdefault(tt_start, [])
            events_by_index[tt_start].append({
                'SUMMARY': event.title,
                'tt_start': tt_start,
                'tt_end': tt_end,
                'resource_id': calendar_name,
                'event_id': str(uid),
                'colspan': tt_end - tt_start + 1})

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
                if current_events and current_events[-1]['tt_end'] >= index:
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
                # Init column
                column =  {'class': None,
                           'colspan': 1,
                           'rowspan': 1,
                           'evt_url': None}
                # Add event
                if event and tt_index == event['tt_start']:
                    go_url = '%s/;edit' % event['event_id']
                    if show_conflicts and uid in conflicts_list:
                        css_class = 'cal_conflict'
                    else:
                        css_class = 'cal_busy'
                    column['class'] = css_class
                    column['colspan'] = event['colspan']
                    column['evt_url'] = go_url
                    column['SUMMARY'] = event['SUMMARY']
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

        # Header columns (one line with header and empty cases with only
        # '+' for daily_view)
        c_date = Date.encode(c_date)
        url = ';new_resource?type=event&dtstart=%s&dtend=%s' % (c_date, c_date)
        url = get_reference(url)
        header_columns = [
            url.replace(start_time=Time.encode(x), end_time=Time.encode(y))
            for x, y in timetables ]

        # Return namespace
        return {
            'name': resource.get_title(),
            'rows': rows_namespace,
            'header_columns': header_columns,
            'url': ';monthly_view?date=%s' % c_date,
            'rowspan': len(rows) + 1}


    @thingy_lazy_property
    def timetables(self):
        """Build a list of timetables represented as tuples(start, end).
        Interval is given by minutes.
        """
        start_time, end_time, interval = self.get_cal_range()

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


    def calendars(self):
        return [self.get_ns_calendar(self.c_date, self.timetables)]


    def header_timetables(self):
        timetables = self.timetables
        c_date = self.c_date

        # Table heading and footer with the time ranges
        delta = timedelta(minutes=45)
        tt_start, tt_end = timetables[0]
        last_start = datetime.combine(c_date, tt_start)
        ns_timetables = [last_start.strftime('%H:%M')]
        # Add next ones if delta time > delta minutes
        for tt_start, tt_end in timetables[1:]:
            tt_start = datetime.combine(c_date, tt_start)
            if (tt_start - last_start) > delta:
                ns_timetables.append(tt_start.strftime('%H:%M'))
                last_start = tt_start
            else:
                ns_timetables.append(None)

        return ns_timetables



class Calendar_Upload(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Replace')
    template = '/ui/calendar/upload.xml'
    file = file_field(required=True)


    def action(self, resource, context, form):
        file = form['file']
        filename, mimetype, body = file

        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
        if mimetype != 'text/calendar':
            message = u'Unexpected file of mimetype {mimetype}.'
            context.message = ERROR(message, mimetype=mimetype)
            return

        # Replace
        try:
            handler.load_state_from_ical_file(StringIO(body))
        except:
            message = ERROR(u'Failed to load the file, may contain errors.')
            context.message = message
        else:
            context.server.change_resource(resource)
            context.message = INFO(u'Version uploaded')



class Calendar_Download(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        response = context.response
        # Filename
        filename = "%s.ics" % resource.name
        response.set_header('Content-Disposition',
                            'inline; filename="%s"' % filename)
        # Content-Type
        response.set_header('Content-Type', 'text/calendar')
        return resource.handler.to_ical()
