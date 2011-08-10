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
from calendar import monthrange
from cStringIO import StringIO
from datetime import date, datetime, time, timedelta
from operator import itemgetter

# Import from itools
from itools.core import proto_lazy_property
from itools.datatypes import Date, Integer
from itools.gettext import MSG
from itools.ical import Time
from itools.stl import stl
from itools.uri import encode_query, get_reference
from itools.web import BaseView, STLView, get_context, INFO, ERROR
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from event import Event
from grid import get_grid_data
from ikaaro import messages
from ikaaro.database import Database
from ikaaro.datatypes import FileDataType
from ikaaro.folder_views import Folder_NewResource
from ikaaro.utils import CMSTemplate

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



def get_current_date(value):
    """Get date as a date object from string value.
    By default, get today's date as a date object.
    """
    if value is None:
        return date.today()
    try:
        return Date.decode(value)
    except ValueError:
        return date.today()



class TimetablesForm(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Timetables')
    template = '/ui/calendar/edit_timetables.xml'
    styles = ['/ui/calendar/style.css']


    def get_namespace(self, resource, context):
        # Show current timetables only if previously set in metadata
        if resource.has_property('timetables'):
            timetables = resource.get_value('timetables')
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
        timetables = resource.get_value('timetables')
        if (start, end) in timetables:
            context.message = ERROR(u'The given range is already defined.')
            return

        # Add new range
        timetables.append((start, end))
        timetables.sort()
        resource.set_value('timetables', timetables)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED


    action_remove_schema = {'ids': Integer(multiple=True)}
    def action_remove(self, resource, context, form):
        ids = form['ids']
        if len(ids) == 0:
            context.message = ERROR(u'Nothing to remove.')
            return

        # New timetables
        timetables = resource.get_value('timetables')
        timetables = [
            timetable for index, timetable in enumerate(timetables)
            if index not in ids ]
        resource.set_property('timetables', timetables)
        # Ok
        context.message = INFO(u'Timetable(s) removed successfully.')


    def action_update(self, resource, context, form):
        timetables = resource.get_value('timetables')
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
        resource.set_property('timetables', new_timetables)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CalendarSelectorTemplate(CMSTemplate):

    template = '/ui/calendar/cal_selector.xml'
    c_date = None
    method = None

    def make_link(self, title, date, method=None):
        if method is None:
            method = self.method
        # Build link
        link = ';{method}?start={date}&end={date}'
        link = link.format(date=Date.encode(date), method=method)
        # Enabled ?
        enabled = self.method == method
        return {'title': title,
                'link': link,
                'css': 'enabled' if enabled else ''}


    @proto_lazy_property
    def link_today(self):
        return self.make_link(u'Today', date.today())


    @proto_lazy_property
    def start(self):
        return Date.encode(self.c_date)


    @proto_lazy_property
    def firstday(self):
        return self.context.view.get_first_day()

    titlew1 = MSG(u'{m_start} {w_start}, {y_start} - {m_end} {w_end}, {y_end}')
    titlew2 = MSG(u'{m_start} {w_start} - {m_end} {w_end}, {y_start}')
    titlew3 = MSG(u'{m_start} {w_start} - {w_end}, {y_start}')
    titlem1 = MSG(u'{month} {year}')
    titled1 = MSG(u'{weekday}, {month} {day}, {year}')

    @proto_lazy_property
    def title(self):
        method = self.method
        c_date = self.c_date
        kw = {'weekday': days[c_date.weekday()],
              'day': c_date.day,
              'month' : months[c_date.month],
              'year': c_date.year}
        if method == 'daily_view':
            return self.titled1.gettext(**kw)
        elif method == 'weekly_view':
            week_start = c_date - timedelta(c_date.weekday())
            week_end = week_start + timedelta(days=6)
            kw['w_start'] = week_start.day
            kw['w_end'] = week_end.day
            kw['m_start'] = months[week_start.month]
            kw['m_end'] = months[week_end.month]
            kw['y_start'] = week_start.year
            kw['y_end'] = week_end.year
            if kw['y_end'] > kw['y_start']:
                return self.titlew1.gettext(**kw)
            elif kw['w_end'] < kw['w_start']:
                return self.titlew2.gettext(**kw)
            return self.titlew3.gettext(**kw)
        elif method == 'monthly_view':
            return self.titlem1.gettext(**kw)
        raise ValueError


    @proto_lazy_property
    def navigation_links(self):
        c_date = self.c_date
        method = self.method
        if method == 'daily_view':
            previous_date = c_date - timedelta(1)
            next_date = c_date + timedelta(1)
        elif method == 'weekly_view':
            previous_date = c_date - timedelta(7)
            next_date = c_date + timedelta(7)
        elif method == 'monthly_view':
            delta = 31
            if c_date.month != 1:
                kk, delta = monthrange(c_date.year, c_date.month - 1)
            previous_date = c_date - timedelta(delta)
            kk, delta = monthrange(c_date.year, c_date.month)
            next_date = c_date + timedelta(delta)
        # Return links
        return {'previous': self.make_link(MSG(u'«'), previous_date),
                'next': self.make_link(MSG(u'»'), next_date)}


    @proto_lazy_property
    def calendar_view_links(self):
        return [self.make_link(MSG(u'Day'), self.c_date, 'daily_view'),
                self.make_link(MSG(u'Week'), self.c_date, 'weekly_view'),
                self.make_link(MSG(u'Month'), self.c_date, 'monthly_view')]



class CalendarView(STLView):

    styles = ['/ui/calendar/style.css']
    # default viewed fields on monthly_view
    default_viewed_fields = ('dtstart', 'dtend', 'title', 'status')

    calendar_selector = CalendarSelectorTemplate

    def get_first_day(self):
        """Returns 0 if Sunday is the first day of the week, else 1.
        For now it has to be overridden to return anything else than 1.
        """
        return 1


    def get_with_new_url(self, resource, context):
        ac = resource.get_access_control()
        return ac.is_allowed_to_add(context.user, resource)


    def get_week_number(self, c_date):
        """datetime.strftime('%U') gives week number, starting week by sunday
           datetime.strftime('%W') gives week number, starting week by monday
           This week number is calculated as "Week 1" begins on the first
           sunday/monday of the year. Its range is [0, 53].

        We adjust week numbers to fit rules which are used by French people.
        XXX Check for other countries.
        """
        if self.get_first_day() == 1:
            format = '%W'
        else:
            format = '%U'
        week_number = int(c_date.strftime(format))
        # Get day of 1st January, if < friday and != monday then number++
        day, kk = monthrange(c_date.year, 1)
        if day in (1, 2, 3):
            week_number = week_number + 1
        return week_number


    # Get days of week based on get_first_day's result for start
    def days_of_week_ns(self, start, num=None, ndays=7, selected=None):
        """
          start : start date of the week
          num : True if we want to get number of the day too
          ndays : number of days we want
          selected : selected date
        """
        current_date = start
        ns_days = []
        for index in range(ndays):
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
    def search(self, calendar, **kw):
        # Build the query
        query = AndQuery()
        query.append(PhraseQuery('is_event', True))
        for name, value in kw.items():
            query.append(PhraseQuery(name, value))

        # Search
        return get_context().root.search(query)


    def get_config_calendar(self, resource):
        return resource.get_resource('/config/calendar')


    def get_colors(self, resource):
        return self.get_config_calendar(resource).colors


    def get_color(self, resource, event, colors=None):
        if colors is None:
            colors = self.get_colors(resource)

        # Load or initialize the colors cache
        cache_colors = getattr(self, 'cache_colors', None)
        if cache_colors is None:
            self.cache_colors = {}
            cache_colors = self.cache_colors
        cache_used_colors = getattr(self, 'cache_used_colors', 0)

        # Cache lookup
        organizer = event.get_owner()
        color = cache_colors.get(organizer, None)
        if color is None:
            # Choose color for current organizer
            color = colors[cache_used_colors % len(colors)]
            # Update cache
            cache_colors[organizer] = color
            self.cache_used_colors = cache_used_colors + 1

        return color


    def events_to_namespace(self, resource, events, day, grid=False,
                            show_conflicts=False):
        """Build namespace for events occuring on current day.
        Update events, removing past ones.

        Events is a list of events where each one follows:
          (resource_name, dtstart, event)
          'event' object must have a methods:
              - get_end
              - get_ns_event.
        """
        context = get_context()
        user = context.user
        ac = resource.get_access_control()

        ns_events = []
        events = events.search(dates=day)
        for event in events.get_documents(sort_by='dtstart'):
            e_dtstart = event.dtstart
            if type(e_dtstart) is datetime:
                e_dtstart = e_dtstart.date()
            e_dtend = event.dtend
            if type(e_dtend) is datetime:
                e_dtend = e_dtend.date()

            # Current event occurs on current date
            starts_on = e_dtstart == day
            ends_on = e_dtend == day
            out_on = (e_dtstart < day and e_dtend > day)

            conflicts_list = set()
            if show_conflicts:
                handler = resource.handler
                conflicts = handler.get_conflicts(e_dtstart, e_dtend)
                if conflicts:
                    for uids in conflicts:
                        conflicts_list.update(uids)
            event = resource.get_resource(event.abspath)
            ns_event = event.get_ns_event(conflicts_list, grid, starts_on,
                                          ends_on, out_on)
            if ac.is_allowed_to_view(user, event):
                url = './;proxy?id={id}&view=edit'.format(id=event.name)
            else:
                url = None
            ns_event['url'] = url
            ns_event['cal'] = 0
            ns_event['color'] = self.get_color(resource, event, None)
            ns_event.setdefault('resource', {})['color'] = 0
            ns_events.append(ns_event)

        return ns_events


    def get_namespace(self, resource, context, c_date, method=None, ndays=7):
        namespace = {}
        if method is not None and self.calendar_selector:
            # Add header to navigate into time
            namespace['cal_selector'] = self.calendar_selector(
                method=method, context=context, c_date=c_date)
        return namespace



class MonthlyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Monthly View')
    template = '/ui/calendar/monthly_view.xml'
    monthly_template = '/ui/calendar/monthly_template.xml'


    def get_namespace(self, resource, context, ndays=7):
        today_date = date.today()

        # Current date
        c_date = context.get_form_value('start')
        c_date = get_current_date(c_date)
        # Save selected date
        context.set_cookie('selected_date', c_date)

        # Method
        method = context.get_cookie('method')
        if method != 'monthly_view':
            context.set_cookie('method', 'monthly_view')
        # Display link to add/edit an event
        with_new_url = self.get_with_new_url(resource, context)

        ###################################################################
        # Calculate start of previous week
        # 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(7 + weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)

        ###################################################################
        # Get a list of events to display on view
        events = self.search(resource)
        template = self.monthly_template
        if type(template) is str:
            template = context.get_template(template)

        ###################################################################
        namespace = super(MonthlyView, self).get_namespace(resource, context,
                c_date, 'monthly_view', ndays)
        # Get header line with days of the week
        namespace['days_of_week'] = self.days_of_week_ns(start, ndays=ndays)

        namespace['weeks'] = []
        day = start
        # 5 weeks
        link = ';new_event?dtstart={date}&dtend={date}'
        for w in range(5):
            ns_week = {'days': [], 'month': u''}
            # 7 days a week
            for d in range(7):
                # day in timetable
                if d < ndays:
                    ns_day = {
                        'url': None,
                        'nday': day.day,
                        'selected': (day == today_date)}
                    if with_new_url:
                        ns_day['url'] = link.format(date=Date.encode(day))
                    # Insert events
                    ns_events = self.events_to_namespace(resource, events,
                                                         day)
                    ns_day['events'] = stl(template, {'events': ns_events})
                    ns_week['days'].append(ns_day)
                    if day.day == 1:
                        month = months[day.month].gettext()
                        ns_week['month'] = month
                day = day + timedelta(1)
            namespace['weeks'].append(ns_week)

        namespace['add_icon'] = '/ui/icons/16x16/add.png'
        return namespace



class WeeklyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Weekly View')
    template = '/ui/calendar/weekly_view.xml'


    def get_weekly_templates(self):
        """Get weekly templates to display events with timetables, and full
        day events.
        """
        return None, None


    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self, resource, start_date):
        """Build namespace to give as grid to gridlayout factory.
        """
        timetables = self.get_config_calendar(resource).get_timetables()

        ns_timetables = []
        for start, end in timetables:
            for value in (start, end):
                value = Time.encode(value)
                if value not in ns_timetables:
                    ns_timetables.append(value)
        return ns_timetables


    def get_grid_events(self, resource, current_date, ndays=7, headers=None,
                        step=timedelta(1)):
        """Build namespace to give as data to gridlayout factory.
        """
        # Get events by day
        ns_days = []

        if headers is None:
            headers = [None] * ndays

        # For each found calendar (or self), get events
        events = []
        # Get a list of events to display on view
        events = self.search(resource)
        for header in headers:
            # Insert events
            ns_events = self.events_to_namespace(resource, events,
                                                 current_date, grid=True)
            ns_days.append({'header': header, 'events': ns_events})
            current_date += step

        return ns_days


    def get_namespace(self, resource, context, ndays=7):
        # Current date
        c_date = context.get_form_value('start')
        if not c_date:
            c_date = context.get_cookie('selected_date')
        c_date = get_current_date(c_date)
        # Save selected date
        context.set_cookie('selected_date', c_date)

        # Method
        method = context.get_cookie('method')
        if method != 'weekly_view':
            context.set_cookie('method', 'weekly_view')

        # Calculate start of current week: 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)

        namespace = super(WeeklyView, self).get_namespace(resource, context,
                c_date, 'weekly_view')

        # Get icon to appear to add a new event
        add_icon = '/ui/icons/16x16/add.png'
        namespace['add_icon'] = add_icon

        # Get header line with days of the week
        days_of_week_ns = self.days_of_week_ns(start, True, ndays, c_date)
        ns_headers = []
        for day in days_of_week_ns:
            ns_header = '%s %s' % (day['name'], day['nday'])
            # Tip: Use 'selected' for css class to highlight selected date
            ns_headers.append(ns_header)
        # Calculate timetables and events occurring for current week
        timetables = self.get_timetables_grid_ns(resource, start)

        events = self.get_grid_events(resource, start, headers=ns_headers)

        # Fill data with grid (timetables) and data (events for each day)
        templates = self.get_weekly_templates()
        with_new_url = self.get_with_new_url(resource, context)
        timetable = get_grid_data(events, timetables, start, templates,
                                  with_new_url, add_icon)
        namespace['timetable_data'] = timetable

        return namespace



class DailyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Daily View')
    template = '/ui/calendar/daily_view.xml'
    query_schema = {'start': Date}

    # Start 07:00, End 21:00, Interval 30min
    class_cal_range = (time(7,0), time(21,0), 30)
    class_cal_fields = ('title', 'DTSTART', 'DTEND')


    def get_cal_range(self):
        return self.class_cal_range


    # Get namespace for a resource's lines into daily_view
    def get_ns_calendar(self, calendar, c_date, timetables,
            method='daily_view', show_conflicts=False, context=None):
        context = get_context()
        user = context.user
        ac = calendar.get_access_control()
        cal_fields = self.class_cal_fields
        calendar_name = str(calendar.name)
        args = {'start': Date.encode(c_date), 'method': method}

        # Get a dict for each event, compute colspan
        events_by_index = {}
        events = self.search(calendar, dates=c_date)
        for event in events.get_documents(sort_by='dtstart'):
            event = calendar.get_resource(event.abspath)
            event_start = event.get_value('dtstart')
            event_end = event.get_value('dtend')
            # Compute start and end indexes
            tt_start = 0
            tt_end = len(timetables) - 1
            for tt_index, (start, end) in enumerate(timetables):
                start = datetime.combine(c_date, start)
                start = context.fix_tzinfo(start)
                end = datetime.combine(c_date, end)
                end = context.fix_tzinfo(end)
                if start <= event_start:
                    tt_start = tt_index
                if end >= event_end:
                    tt_end = tt_index
                    break

            uid = getattr(event, 'id', getattr(event, 'uid', None))
            if ac.is_allowed_to_view(user, event):
                edit_url = './;proxy?id={id}&view=edit'.format(id=event.name)
            else:
                edit_url = None
            events_by_index.setdefault(tt_start, [])
            events_by_index[tt_start].append({
                'name': event.name,
                'title': event.get_value('title'),
                'tt_start': tt_start,
                'tt_end': tt_end,
                'colspan': tt_end - tt_start + 1,
                'edit_url': edit_url})

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
            conflicts = calendar.handler.get_conflicts(c_date)
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
                tmp_args = args.copy()
                tmp_args['start_time'] = Time.encode(start)
                tmp_args['end_time'] = Time.encode(end)
                # Init column
                column =  {'class': None,
                           'colspan': 1,
                           'rowspan': 1,
                           'evt_url': None}
                # Add event
                if event and tt_index == event['tt_start']:
                    go_url = event['edit_url']
                    if go_url:
                        go_url = '%s&%s' % (go_url, encode_query(args))
                    if show_conflicts and uid in conflicts_list:
                        css_class = 'cal_conflict'
                    else:
                        css_class = 'cal_busy'
                    column['class'] = css_class
                    column['colspan'] = event['colspan']
                    column['evt_url'] = go_url
                    column['title'] = event['title']
                    # Set colspan
                    colspan = event['colspan'] - 1
                    # Delete added event
                    event = events.pop(0) if events else None
                # Fields in template but not shown
                for field in cal_fields:
                    if field not in column:
                        column[field] = None
                columns_namespace.append(column)
                row_namespace['columns'] = columns_namespace
            rows_namespace.append(row_namespace)

        # Header columns (one line with header and empty cases with only
        # '+' for daily_view)
        with_new_url = self.get_with_new_url(calendar, context)
        if with_new_url:
            url = ';new_event?%s' % encode_query(args)
            url = get_reference(url).replace(resource=calendar_name)
            header_columns = [
                url.replace(start_time=Time.encode(x), end_time=Time.encode(y))
                for x, y in timetables ]
        else:
            header_columns = [ None for x, y in timetables ]

        # Return namespace
        return {
            'name': calendar.get_title(),
            'rows': rows_namespace,
            'header_columns': header_columns,
            'url': ';monthly_view?%s' % encode_query(args),
            'rowspan': len(rows) + 1}


    def get_namespace(self, resource, context):
        method = context.get_cookie('method')
        if method != 'daily_view':
            context.set_cookie('method', 'daily_view')

        # Current date
        c_date = context.query['start']
        if c_date is None:
            c_date = date.today()

        # Add a header line with start time of each timetable
        start, end, interval = self.get_cal_range()
        timetables = build_timetables(start, end, interval)

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

        # Ok
        ns_calendar = self.get_ns_calendar(resource, c_date, timetables,
                                           context=context)

        namespace = super(DailyView, self).get_namespace(resource, context,
                c_date, 'daily_view')
        namespace['header_timetables'] = ns_timetables
        namespace['calendars'] = [ns_calendar]

        return namespace



class Calendar_Import(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Import')
    template = '/ui/calendar/upload.xml'
    schema = {
        'file': FileDataType(mandatory=True)}


    def action(self, resource, context, form):
        file = form['file']
        filename, mimetype, body = file

        # Check wether the handler is able to deal with the uploaded file
        if mimetype != 'text/calendar':
            message = messages.MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)
            context.message = message
            return

        # Replace
        try:
            resource.load_state_from_ical_file(StringIO(body))
        except BaseException:
            message = ERROR(u'Failed to load the file, may contain errors.')
            context.message = message
        else:
            context.database.change_resource(resource)
            context.message = INFO(u'Version uploaded')



class Calendar_ExportForm(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'Export')
    template = '/ui/calendar/export_form.xml'

    def get_namespace(self, resource, context):
        return {'filename': '%s.ics' % resource.name}



class Calendar_Export(BaseView):

    access = 'is_allowed_to_view'

    def GET(self, resource, context):
        ical = resource.to_ical(context)
        context.set_content_type('text/calendar')
        context.set_content_disposition('inline', '%s.ics' % resource.name)
        return ical



class Calendar_NewEvent(Folder_NewResource):

    title = MSG(u'Create a new event')


    def get_items(self, resource, context):
        return [ x for x in Database.resources_registry.values()
                 if issubclass(x, Event) ]
