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
from datetime import date, datetime, timedelta

# Import from itools
from itools.core import proto_lazy_property
from itools.datatypes import Date, Integer
from itools.gettext import MSG
from itools.ical import Time
from itools.web import BaseView, STLView, INFO, ERROR
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from event import Event
from grid import get_grid_data
from ikaaro import messages
from ikaaro.config_common import NewResource_Local
from ikaaro.datatypes import FileDataType
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


######################################################################
# Calendar timetables configuration
######################################################################

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


######################################################################
# Calendar Navigation
######################################################################

class CalendarSelectorTemplate(CMSTemplate):

    template = '/ui/calendar/cal_selector.xml'
    c_date = None
    method = None

    def make_link(self, title, date, method=None):
        if method is None:
            method = self.context.view.method
        # Build link
        link = ';{method}?start={date}&end={date}'
        link = link.format(date=Date.encode(date), method=method)
        # Enabled ?
        enabled = self.context.view.method == method
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
        method = self.context.view.method
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
        method = self.context.view.method
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


######################################################################
# Calendar Views
######################################################################

class CalendarView(STLView):

    query_schema = {'start': Date}

    styles = ['/ui/calendar/style.css']
    scripts = ['/ui/calendar/javascript.js']

    calendar_selector = CalendarSelectorTemplate


    def get_first_day(self):
        """Returns 0 if Sunday is the first day of the week, else 1.
        For now it has to be overridden to return anything else than 1.
        """
        return 1


    def get_current_date(self, context):
        return context.query['start'] or date.today()


    def get_with_new_url(self, resource, context):
        return context.root.is_allowed_to_add(context.user, resource)


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
    def get_events(self, day=None, *args):
        query = AndQuery(*args)
        query.append(PhraseQuery('is_event', True))
        if day:
            query.append(PhraseQuery('dates', day))

        # Ok
        search = self.context.search(query)
        return search.get_resources(sort_by='dtstart')


    def get_config_calendar(self, resource):
        return resource.get_resource('/config/calendar')


    def get_namespace(self, resource, context):
        c_date = self.get_current_date(context)
        cal_selector = self.calendar_selector(context=context, c_date=c_date)
        return {'cal_selector': cal_selector,
                'add_icon': '/ui/icons/16x16/add.png'}



class MonthlyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Monthly View')
    template = '/ui/calendar/monthly_view.xml'

    ndays = 7
    method = 'monthly_view'

    def get_start_date(self, c_date):
        # Calculate start of previous week
        # 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(7 + weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)
        return start


    def get_namespace(self, resource, context):
        # Base namespace
        namespace = super(MonthlyView, self).get_namespace(resource, context)
        # Get today date
        today_date = date.today()
        # Current date
        c_date = self.get_current_date(context)
        # Display link to add/edit an event
        with_new_url = self.get_with_new_url(resource, context)
        # Start date
        start = self.get_start_date(c_date)
        # Get header line with days of the week
        namespace['days_of_week'] = self.days_of_week_ns(start, ndays=self.ndays)
        # Get the 5 weeks
        namespace['weeks'] = []
        link = ';new_event?dtstart={date}&dtend={date}'
        day = start
        for w in range(5):
            ns_week = {'days': [], 'month': u''}
            # 7 days a week
            for d in range(7):
                # Day in timetable
                if d < self.ndays:
                    ns_day = {'url': None,
                              'nday': day.day,
                              'selected': (day == today_date)}
                    if with_new_url:
                        ns_day['url'] = link.format(date=Date.encode(day))
                    # Get a list of events to display on view
                    ns_day['events'] = []
                    for event in self.get_events(day):
                        ns_day['events'].append(
                          {'stream': event.render(event=event, day=day),
                           'color': event.get_color(),
                           'status': event.get_value('status') or 'cal_busy'})
                    ns_week['days'].append(ns_day)
                    if day.day == 1:
                        ns_week['month'] = months[day.month].gettext()
                day = day + timedelta(1)
            namespace['weeks'].append(ns_week)
        return namespace



class WeeklyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Weekly View')
    template = '/ui/calendar/weekly_view.xml'

    css_id = 'cal-weekly-view'
    method = 'weekly_view'
    ndays = 7

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

        # Get a list of events to display on view
        for header in headers:
            # Insert events
            ns_events = []
            for event in self.get_events(current_date):
                n = event.get_ns_event(current_date, grid=True)
                n['stream'] = event.render(event=event, day=current_date)
                ns_events.append(n)
            ns_days.append({'header': header, 'events': ns_events})
            current_date += step

        return ns_days


    def get_start_date(self, c_date):
        # Calculate start of current week: 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)
        return start


    def get_namespace(self, resource, context):
        # Base namespace
        namespace = super(WeeklyView, self).get_namespace(resource, context)

        # Current date
        c_date = self.get_current_date(context)

        # Start date
        start = self.get_start_date(c_date)

        # Get header line with days of the week
        days_of_week_ns = self.days_of_week_ns(start, True, self.ndays, c_date)
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
                                  with_new_url, namespace['add_icon'])
        namespace['timetable_data'] = timetable
        namespace['css_id'] = self.css_id

        return namespace



class DailyView(WeeklyView):

    access = 'is_allowed_to_view'
    title = MSG(u'Daily View')

    ndays = 1
    css_id = 'cal-daily-view'
    method = 'daily_view'

    def get_start_date(self, c_date):
        return c_date


######################################################################
# Calendar Utils Views
######################################################################

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



class Calendar_NewEvent(NewResource_Local):

    title = MSG(u'Create a new event')

    document_types = (Event,)
