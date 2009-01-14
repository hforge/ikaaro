# -*- coding: UTF-8 -*-
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Gautier Hayoun <gautier.hayoun@itaapy.com>
# Copyright (C) 2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from the Standard Library
from datetime import time, timedelta

# Import from itools
from itools.csv import Table as BaseTable, Record
from itools.datatypes import DateTime, String, Unicode, Enumerate
from itools.gettext import MSG
from itools.ical import Time
from itools.utils import freeze
from itools.web import get_context
from itools.xapian import OrQuery, AndQuery, RangeQuery

# Import from ikaaro
from ikaaro.calendar_ import CalendarBase
from ikaaro.calendar_views import MonthlyView
from ikaaro.calendar_views import WeeklyView
from ikaaro.forms import DateWidget, MultilineWidget, SelectWidget, TextWidget
from ikaaro.table import Table
from ikaaro.registry import register_resource_class

# Import from ikaaro.tracker
from tracker_views import Tracker_View


resolution = timedelta.resolution


class TrackerMonthlyView(MonthlyView):

    monthly_template = '/ui/tracker/monthly_template.xml'
    query_schema = Tracker_View.tracker_schema

    def get_with_new_url(self):
        return False


    def get_namespace(self, resource, context):
        context.styles.append('/ui/tracker/tracker.css')
        return MonthlyView.get_namespace(self, resource, context)



class TrackerWeeklyView(WeeklyView):

    weekly_template_fd = '/ui/tracker/weekly_template_fd.xml'
    weekly_template = '/ui/tracker/weekly_template.xml'
    query_schema = Tracker_View.tracker_schema


    def get_weekly_templates(self):
        root = get_context().root
        template = root.get_resource(self.weekly_template)
        template_fd = root.get_resource(self.weekly_template_fd)
        return template, template_fd


    def get_with_new_url(self):
        return False


    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self, resource, start_date):
        """Build namespace to give as grid to gridlayout factory.
        """
        ns_timetables = []
        for start, end in resource.get_timetables():
            for value in (start, end):
                value = Time.encode(value)
                if value not in ns_timetables:
                    ns_timetables.append(value)
        return ns_timetables


    def get_namespace(self, resource, context):
        context.styles.append('/ui/tracker/tracker.css')
        return WeeklyView.get_namespace(self, resource, context)



class Resource(Record):

    def get_end(self):
        return self.get_value('dtend')


    def get_ns_event(self, day, resource_name=None, conflicts_list=freeze([]),
                     timetable=None, grid=False, starts_on=True, ends_on=True,
                     out_on=True):
        context = get_context()
        tracker = context.resource.parent
        issue = tracker.get_resource(self.get_value('issue'))
        comment = self.get_value('comment')

        users = context.root.get_resource('/users')
        user = self.get_value('resource')
        user_title = users.get_resource(user).get_title()

        products = tracker.get_resource('product').handler
        product = issue.get_value('product')
        product = products.get_record(product)
        product = products.get_record_value(product, 'title')

        ns = {}
        ns['resource'] = {'name': user, 'title': user_title}

        ns['issue'] = {'number': issue.name, 'title': issue.get_value('title'),
                       'url': '../%s/;edit' % issue.name, 'product': product,
                       'comment': comment}

        ###############################################################
        # Set dtstart and dtend values using '...' for events which
        # appear into more than one cell
        start = self.get_value('dtstart')
        end = self.get_value('dtend')
        ns['start'] = Time.encode(start.time())
        ns['end'] = Time.encode(end.time())
        ns['TIME'] = None
        if grid:
            # Neither a full day event nor a multiple days event
            if start.time() != time(0,0) and end.time() != time(0,0)\
              and start.date() == end.date():
                ns['TIME'] = '%s - %s' % (ns['start'], ns['end'])
            else:
                ns['start'] = ns['end'] = None
        elif not out_on:
            if start.date() != end.date():
                value = ''
                if starts_on:
                    value = ns['start']
                    if ends_on:
                        value = value + '-'
                    else:
                        value = value + '...'
                if ends_on:
                    value = value + ns['end']
                    if not starts_on:
                        value = '...' + value
                ns['TIME'] = '(' + value + ')'

        return ns



class ListOfUsers(Enumerate):

    @classmethod
    def get_options(cls):
        tracker = get_context().resource.parent
        return [{'name': x['id'], 'value': x['title']}
                for x in tracker.get_members_namespace('')]



class BaseResources(BaseTable):

    record_schema = {
        'dtstart': DateTime(mandatory=True, index='keyword'),
        'dtend': DateTime(mandatory=True, index='keyword'),
        'issue': String(mandatory=True, index='keyword'),
        'resource': ListOfUsers(mandatory=True, index='keyword'),
        'comment': Unicode}

    form = [
        SelectWidget('resource', title=MSG(u'Resource')),
        DateWidget('dtstart', title=MSG(u'Start YYYY-MM-DD HH:MM')),
        DateWidget('dtend', title=MSG(u'End')),
        MultilineWidget('comment', title=MSG(u'Comment')),
        TextWidget('issue', title=MSG(u'Issue'))]

    record_class = Resource



class Resources(Table, CalendarBase):

    class_id = 'tracker_calendar'
    class_version = '20071216'
    class_title = MSG(u'Resources')
    class_description = MSG(u'Resources assigned to issues')
    class_handler = BaseResources

    class_views = ['weekly_view', 'monthly_view', 'edit_timetables']


    def get_action_url(self, **kw):
        issue = kw.get('issue', None)
        if issue:
            return get_context().uri.resolve('../%s/;edit' % issue)
        return None


    def get_events_to_display(self, start, end):
        # Build the query
        dtstart = str(start)
        dtend = str(end)
        dtstart_limit = str(start + resolution)
        dtend_limit = str(end + resolution)
        query = OrQuery(RangeQuery('dtstart', dtstart, dtend),
                        RangeQuery('dtend', dtstart_limit, dtend_limit),
                        AndQuery(RangeQuery('dtstart', None, dtstart),
                                 RangeQuery('dtend', dtend, None)))

        # Define the set of concerned issues
        tracker = self.parent
        issues = tracker.get_search_results(get_context())
        issues = [ x.name for x in issues.get_documents() ]

        # Find out the events
        handler = self.handler
        events = [
            (0, handler.get_record_value(x, 'dtstart'), x)
            for x in handler.search(query)
            if handler.get_record_value(x, 'issue') in issues ]
        events.sort(lambda x, y: cmp(x[1], y[1]))

        # Ok
        return {0: self.name}, events


    monthly_view = TrackerMonthlyView()
    weekly_view = TrackerWeeklyView()




###########################################################################
# Register
###########################################################################
register_resource_class(Resources)
