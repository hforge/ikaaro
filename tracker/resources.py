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
from itools.datatypes import DateTime, String, Unicode
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.html import XHTMLFile
from itools.ical import Time
from itools.web import get_context
from itools.xapian import OrQuery, AndQuery, RangeQuery

# Import from ikaaro
from ikaaro.calendar_views import CalendarView, MonthlyView, TimetablesForm
from ikaaro.calendar_views import WeeklyView
from ikaaro.forms import DateWidget, MultilineWidget, Select, TextWidget
from ikaaro.table import Table
from ikaaro.registry import register_object_class


resolution = timedelta.resolution

# Template to display events on monthly_view
template_string = """
  <table xmlns:stl="http://xml.itools.org/namespaces/stl"
         xmlns="http://www.w3.org/1999/xhtml" class="event">
    <tr stl:repeat="event events" class="color0">
      <td>
        <a href="${event/url}">[#${event/issue/number}]</a>
        ${event/issue/title}
        <span stl:if="event/TIME" class="time">${event/TIME}</span>
        (${event/resource/title})
      </td>
    </tr>
  </table>
"""
monthly_template = XHTMLFile()
monthly_template.load_state_from_string(template_string)


# Template to display full day events
template_string = """
  <td xmlns="http://www.w3.org/1999/xhtml" class="color0">
    <a href="${issue/url}">[#${issue/number}]</a>
    ${issue/title}
    (${resource/title})
  </td>
"""
template_fd = XHTMLFile()
template_fd.load_state_from_string(template_string)


# Template to display events with timetables
template_string = """
  <td xmlns="http://www.w3.org/1999/xhtml" colspan="${cell/colspan}"
    rowspan="${cell/rowspan}" valign="top" class="color0">
      <a href="${cell/content/issue/url}">[#${cell/content/issue/number}]</a>
      ${cell/content/issue/title}
      (${cell/content/resource/title})
  </td>
"""
template = XHTMLFile()
template.load_state_from_string(template_string)



class TrackerView(CalendarView):

    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self, start_date):
        """Build namespace to give as grid to gridlayout factory.
        """
        ns_timetables = []
        for start, end in self.get_timetables():
            for value in (start, end):
                value = Time.encode(value)
                if value not in ns_timetables:
                    ns_timetables.append(value)
        return ns_timetables


    def get_monthly_template(self):
        return monthly_template


    def get_weekly_templates(self):
        return template, template_fd


    def get_with_new_url(self):
        return False



class Resource(Record):

    def get_end(self):
        return self.get_value('dtend')


    def get_ns_event(self, day, resource_name=None, conflicts_list=[],
                     timetable=None, grid=False,
                     starts_on=True, ends_on=True, out_on=True):
        context = get_context()
        here = context.resource
        issue = here.parent.get_resource(self.get_value('issue'))
        users = context.root.get_resource('/users')
        user = self.get_value('resource')
        user_title = users.get_resource(user).get_title()
        ns = {}
        ns['resource'] = {'name': user, 'title': user_title}
        ns['issue'] = {'number': issue.name, 'title': issue.get_value('title'),
                       'url': '../%s/;edit' % issue.name}

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

    schema = {
        'dtstart': DateTime(mandatory=True, index='keyword'),
        'dtend': DateTime(mandatory=True, index='keyword'),
        'issue': String(mandatory=True, index='keyword'),
        'resource': ListOfUsers(mandatory=True, index='keyword'),
        'comment': Unicode}

    form = [
        Select('resource', title=u'Resource'),
        DateWidget('dtstart', title=u'Start YYYY-MM-DD HH:MM'),
        DateWidget('dtend', title=u'End'),
        MultilineWidget('comment', title=u'Comment'),
        TextWidget('issue', title=u'Issue')]

    record_class = Resource



class Resources(Table, TrackerView):

    class_id = 'resources'
    class_version = '20071216'
    class_title = MSG(u'Resources')
    class_description = MSG(u'Resources assigned to issues')
    class_handler = BaseResources

    class_views = ['weekly_view', 'monthly_view', 'edit_timetables']


    @classmethod
    def get_metadata_schema(cls):
        schema = Table.get_metadata_schema()
        schema.update(TrackerView.get_metadata_schema())
        return schema


    def get_action_url(self, **kw):
        issue = kw.get('issue', None)
        if issue:
            return get_context().uri.resolve('../%s/;edit' % issue)
        return None


    def get_events_to_display(self, start, end):
        results = self.parent.get_search_results(get_context())
        results = [result.name for result in results]
        dtstart = str(start)
        dtend = str(end)
        dtstart_limit = str(start + resolution)
        dtend_limit = str(end + resolution)
        query = OrQuery(RangeQuery('dtstart', dtstart, dtend),
                        RangeQuery('dtend', dtstart_limit, dtend_limit),
                        AndQuery(RangeQuery('dtstart', None, dtstart),
                                 RangeQuery('dtend', dtend, None)))
        resources = self.handler.search(query)

        resource_names, events = {}, []
        for record in resources:
            if record.get_value('issue') in results:
                e_dtstart = record.get_value('dtstart')
                events.append((0, e_dtstart, record))
        events.sort(lambda x, y : cmp(x[1], y[1]))
        return {0:self.name}, events


    monthly_view = MonthlyView()
    weekly_view = WeeklyView()
    edit_timetables = TimetablesForm()


###########################################################################
# Register
###########################################################################
register_object_class(Resources)
