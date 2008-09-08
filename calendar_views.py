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
from datetime import date, timedelta

# Import from itools
from itools.csv import Property
from itools.datatypes import Date, Enumerate, Integer, Unicode
from itools.gettext import MSG
from itools.ical import get_grid_data
from itools.ical import DateTime, Time
from itools.stl import stl
from itools.web import BaseView, STLForm, STLView, get_context

# Import from ikaaro
from file import FileView, FileUpload
from table import Multiple


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


def check_timetable_entry(context, key_start, key_end):
    """Check if timetable built from given key value is valid or not.
    """
    start = context.get_form_value(key_start)
    end = context.get_form_value(key_end)
    if not start or start == '__:__' or not end or end == '__:__':
        return MSG(u'Wrong time selection.')
    try:
        start = Time.decode(start)
        end = Time.decode(end)
    except ValueError:
        return MSG(u'Wrong time selection (HH:MM).')
    if start >= end:
        return MSG(u'Start time must be earlier than end time.')
    return (start, end)



class Status(Enumerate):

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class TimetablesForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Timetables')
    icon = 'settings.png'
    template = '/ui/ical/ical_edit_timetables.xml'
    schema = {}


    def get_namespace(self, resource, context):
        # Initialization
        namespace = {'timetables': []}

        # Show current timetables only if previously set in metadata
        if resource.has_property('timetables'):
            timetables = resource.get_property('timetables')
            for index, (start, end) in enumerate(timetables):
                ns = {}
                ns['index'] = index
                ns['startname'] = '%s_start' % index
                ns['endname'] = '%s_end' % index
                ns['start'] = Time.encode(start)
                ns['end'] = Time.encode(end)
                namespace['timetables'].append(ns)
        return namespace


    def action(self, resource, context, form):
        timetables = []
        if resource.has_property('timetables'):
            timetables = resource.get_property('timetables')

        # Nothing to change
        if timetables == [] and not context.has_form_value('add'):
            context.message = u'Nothing to change.'
            return

        # Remove selected lines
        if context.has_form_value('remove'):
            ids = context.get_form_values('ids')
            if ids == []:
                return context.come_back(MSG(u'Nothing to remove.'))
            new_timetables = []
            for index, timetable in enumerate(timetables):
                if str(index) not in ids:
                    new_timetables.append(timetable)
            context.message = u'Timetable(s) removed successfully.'
        else:
            new_timetables = []
            # Update timetable or just set index to next index
            for index in range(len(timetables)):
                timetable = check_timetable_entry(context, '%s_start' % index,
                                                           '%s_end' % index)
                if not isinstance(timetable, tuple):
                    return context.come_back(timetable)
                new_timetables.append(timetable)

            # Add a new timetable
            if context.has_form_value('add'):
                timetable = check_timetable_entry(context, 'new_start',
                                                           'new_end')
                if not isinstance(timetable, tuple):
                    return context.come_back(timetable)
                new_timetables.append(timetable)

            new_timetables.sort()
            context.message = u'Timetables updated successfully.'

        resource.set_property('timetables', tuple(new_timetables))



class CalendarView(STLView):

    class_weekly_shown = ('SUMMARY', )

    # default values for fields within namespace
    default_fields = {
        'UID': None, 'SUMMARY': u'', 'LOCATION': u'', 'DESCRIPTION': u'',
        'DTSTART_year': None, 'DTSTART_month': None, 'DTSTART_day': None,
        'DTSTART_hours': '', 'DTSTART_minutes': '',
        'DTEND_year': None, 'DTEND_month': None, 'DTEND_day': None,
        'DTEND_hours': '', 'DTEND_minutes': '',
        'ATTENDEE': [], 'COMMENT': [], 'STATUS': {}
      }

    # default viewed fields on monthly_view
    default_viewed_fields = ('DTSTART', 'DTEND', 'SUMMARY', 'STATUS')


    @classmethod
    def get_weekly_shown(cls):
        return cls.class_weekly_shown


    def get_first_day(self):
        """Returns 0 if Sunday is the first day of the week, else 1.
        For now it has to be overridden to return anything else than 1.
        """
        return 1


    def get_with_new_url(self):
        return True


    def add_selector_ns(self, c_date, method, namespace):
        """Set header used to navigate into time.

          datetime.strftime('%U') gives week number, starting week by Sunday
          datetime.strftime('%W') gives week number, starting week by Monday
          This week number is calculated as "Week O1" begins on the first
          Sunday/Monday of the year. Its range is [0,53].

        We adjust week numbers to fit rules which are used by french people.
        XXX Check for other countries
        """
        resource = get_context().resource
        if self.get_first_day() == 1:
            format = '%W'
        else:
            format = '%U'
        week_number = Unicode.encode(c_date.strftime(format))
        # Get day of 1st January, if < friday and != monday then number++
        day, kk = monthrange(c_date.year, 1)
        if day in (1, 2, 3):
            week_number = str(int(week_number) + 1)
            if len(week_number) == 1:
                week_number = '0%s' % week_number
        current_week = MSG(u'Week $n').gettext(n=week_number)
        tmp_date = c_date - timedelta(7)
        previous_week = ";%s?date=%s" % (method, Date.encode(tmp_date))
        tmp_date = c_date + timedelta(7)
        next_week = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Month
        current_month = months[c_date.month].gettext()
        delta = 31
        if c_date.month != 1:
            kk, delta = monthrange(c_date.year, c_date.month - 1)
        tmp_date = c_date - timedelta(delta)
        previous_month = ";%s?date=%s" % (method, Date.encode(tmp_date))
        kk, delta = monthrange(c_date.year, c_date.month)
        tmp_date = c_date + timedelta(delta)
        next_month = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Year
        date_before = date(c_date.year, 2, 28)
        date_after = date(c_date.year, 3, 1)
        delta = 365
        if (isleap(c_date.year - 1) and c_date <= date_before) \
          or (isleap(c_date.year) and c_date > date_before):
            delta = 366
        tmp_date = c_date - timedelta(delta)
        previous_year = ";%s?date=%s" % (method, Date.encode(tmp_date))
        delta = 365
        if (isleap(c_date.year) and c_date <= date_before) \
          or (isleap(c_date.year +1) and c_date >= date_after):
            delta = 366
        tmp_date = c_date + timedelta(delta)
        next_year = ";%s?date=%s" % (method, Date.encode(tmp_date))
        # Set value into namespace
        namespace['current_week'] = current_week
        namespace['previous_week'] = previous_week
        namespace['next_week'] = next_week
        namespace['current_month'] = current_month
        namespace['previous_month'] = previous_month
        namespace['next_month'] = next_month
        namespace['current_year'] = c_date.year
        namespace['previous_year'] = previous_year
        namespace['next_year'] = next_year
        # Add today link
        tmp_date = date.today()
        namespace['today'] = ";%s?date=%s" % (method, Date.encode(tmp_date))
        return namespace


    # Get days of week based on get_first_day's result for start
    def days_of_week_ns(self, start, num=None, ndays=7, selected=None):
        """
          start : start date of the week
          num : True if we want to get number of the day too
          ndays : number of days we want
          selected : selected date
        """
        resource = get_context().resource
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

    def get_action_url(self, **kw):
        """Action to call on form submission.
        """
        return None


    def get_calendars(self):
        """List of sources from which taking events.
        """
        return []


    def get_events_to_display(self, start, end):
        """Get a list of events as tuples (resource_name, start, properties{})
        and a dict with all resources from whom they belong to.
        """
        resources, events = {}, []
        resource = get_context().resource
        for index, calendar in enumerate(resource.get_calendars()):
            res, evts = calendar.get_events_to_display(start, end)
            events.extend(evts)
            resources[calendar.name] = index
        events.sort(lambda x, y : cmp(x[1], y[1]))
        return resources, events


    def events_to_namespace(self, resource, events, day, cal_indexes,
                            grid=False, show_conflicts=False):
        """Build namespace for events occuring on current day.
        Update events, removing past ones.

        Events is a list of events where each one follows:
          (resource_name, dtstart, event)
          'event' object must have a methods:
              - get_end
              - get_ns_event.
        """
        ns_events = []
        index = 0
        while index < len(events):
            resource_name, dtstart, event = events[index]
            e_dtstart = dtstart.date()
            e_dtend = event.get_end().date()
            # Current event occurs on current date
            # event begins during current tt
            starts_on = e_dtstart == day
            # event ends during current tt
            ends_on = e_dtend == day
            # event begins before and ends after
            out_on = (e_dtstart < day and e_dtend > day)

            if starts_on or ends_on or out_on:
                cal_index = cal_indexes[resource_name]
                if len(cal_indexes.items()) < 2:
                    resource_name = None
                if resource_name is not None:
                    current_resource = self.get_object(resource_name)
                else:
                    current_resource = resource
                conflicts_list = set()
                if show_conflicts:
                    handler = current_resource.handler
                    conflicts = handler.get_conflicts(e_dtstart, e_dtend)
                    if conflicts:
                        for uids in conflicts:
                            conflicts_list.update(uids)
                ns_event = event.get_ns_event(day, resource_name=resource_name,
                                              conflicts_list=conflicts_list,
                                              grid=grid, starts_on=starts_on,
                                              ends_on=ends_on, out_on=out_on)
                ns_event['url'] = current_resource.get_action_url(**ns_event)
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



class EditEventForm(CalendarView, STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Event')
    icon = 'button_calendar.png'
    template = '/ui/ical/ical_edit_event.xml'
    schema = {
        'DTSTART_day': Integer(mandatory=True),
        'DTSTART_month': Integer(mandatory=True),
        'DTSTART_year': Integer(mandatory=True),
        'DTSTART_hours': Integer(),
        'DTSTART_minutes': Integer(),
        'DTEND_day': Integer(mandatory=True),
        'DTEND_month': Integer(mandatory=True),
        'DTEND_year': Integer(mandatory=True),
        'DTEND_hours': Integer(),
        'DTEND_minutes': Integer(),
        'SUMMARY': Unicode(mandatory=True),
        'DESCRIPTION': Unicode(),
        'STATUS': Status(mandatory=True),
        }


    @classmethod
    def get_defaults(cls, selected_date=None, tt_start=None, tt_end=None):
        """Return a dic with default values for default fields.
        """
        # Default values for DTSTART and DTEND
        default = cls.default_fields.copy()

        if selected_date:
            year, month, day = selected_date.split('-')
            default['DTSTART_year'] = default['DTEND_year'] = year
            default['DTSTART_month'] = default['DTEND_month'] = month
            default['DTSTART_day'] = default['DTEND_day'] = day
        if tt_start:
            hours, minutes = Time.encode(tt_start).split(':')
            default['DTSTART_hours'] = hours
            default['DTSTART_minutes'] = minutes
        if tt_end:
            hours, minutes = Time.encode(tt_end).split(':')
            default['DTEND_hours'] = hours
            default['DTEND_minutes'] = minutes

        return default


    def get_namespace(self, resource, context):
        uid = context.get_form_value('id')
        # Method
        method = context.get_cookie('method') or 'monthly_view'
        goto = ';%s' % method

        # Get date to add event
        selected_date = context.get_form_value('date')
        if uid is None:
            if not selected_date:
                message = u'To add an event, click on + symbol from the views.'
                message = MSG(message)
                return context.come_back(message, goto=goto)
        else:
            # Get it as a datetime object
            if not selected_date:
                c_date = get_current_date(selected_date)
                selected_date = Date.encode(c_date)

        # Timetables
        tt_start = context.get_form_value('start_time', type=Time)
        tt_end = context.get_form_value('end_time', type=Time)

        # Initialization
        namespace = {}
        namespace['remove'] = None
        namespace['resources'] = namespace['resource'] = None
        properties = []
        status = Status()

        # Existant event
        object = None
        if uid is not None:
            id = uid
            if '/' in uid:
                name, id = uid.split('/')
                if not resource.has_resource(name):
                    message = MSG(u'Invalid argument.')
                    return context.come_back(message, keep=True,
                                             goto=';edit_event')
                object = resource.get_resource(name)
            else:
                object = resource

            # UID is used to remind which object/id is being modified
            namespace['UID'] = uid

            if id != '':
                event = object.get_record(id)
                if event is None:
                    message = MSG(u'Event not found')
                    return context.come_back(message, goto=goto)
                namespace['remove'] = True
                properties = event.get_property()
                # Get values
                for key in properties:
                    if key == 'UID':
                        continue
                    value = properties[key]
                    if isinstance(value, list):
                        namespace[key] = value
                    elif key == 'STATUS':
                        namespace['STATUS'] = value.value
                    # Split date fields into dd/mm/yyyy and hh:mm
                    elif key in ('DTSTART', 'DTEND'):
                        value, params = value.value, value.parameters
                        year, month, day = Date.encode(value).split('-')
                        namespace['%s_year' % key] = year
                        namespace['%s_month' % key] = month
                        namespace['%s_day' % key] = day
                        param = params.get('VALUE', '')
                        if not param or param != ['DATE']:
                            hours, minutes = Time.encode(value).split(':')
                            namespace['%s_hours' % key] = hours
                            namespace['%s_minutes' % key] = minutes
                        else:
                            namespace['%s_hours' % key] = ''
                            namespace['%s_minutes' % key] = ''
                    else:
                        namespace[key] = value.value
            else:
                event = None

        if not uid:
            event = None
            # Selected calendar
            ns_calendars = []
            for calendar in resource.get_calendars():
                ns_calendars.append({'name': calendar.name,
                                     'value': calendar.get_title(),
                                     'selected': False})
            namespace['resources'] = ns_calendars

        # Default managed fields are :
        # SUMMARY, LOCATION, DTSTART, DTEND, DESCRIPTION,
        # STATUS ({}), ATTENDEE ([]), COMMENT ([])
        defaults = self.get_defaults(selected_date, tt_start, tt_end)
        # Set values from context or default, if not already set
        for field in defaults:
            if field not in namespace:
                if field.startswith('DTSTART_') or field.startswith('DTEND_'):
                    for attr in ('year', 'month', 'day', 'hours', 'minutes'):
                        key = 'DTSTART_%s' % attr
                        if field.startswith('DTEND_'):
                            key = 'DTEND_%s' % attr
                        default = defaults[key]
                        value = context.get_form_value(key, default=default)
                        namespace[key] = value
                # Get value from context, used when invalid input given
                elif context.has_form_value(field):
                    namespace[field] = context.get_form_value(field)
                else:
                    # Set default value in the right format
                    namespace[field] = defaults[field]
        # STATUS is an enumerate
        try:
            namespace['STATUS'] = status.get_namespace(namespace['STATUS'])
        except:
            namespace['STATUS'] = status.get_namespace('TENTATIVE')
        # Call to gettext on Status values
        for value in namespace['STATUS']:
            value['value'] = value['value'].gettext()

        # Show action buttons only if current user is authorized
        if object is None:
            namespace['allowed'] = True
        else:
            namespace['allowed'] = object.is_organizer_or_admin(context, event)
        # Set first day of week
        namespace['firstday'] = self.get_first_day()

        return namespace


    action_edit_event__access__ = 'is_allowed_to_edit'
    def action_edit_event(self, resource, context, form):
        goto = ';%s' % context.get_cookie('method') or 'monthly_view'

        # Get selected_date from the 3 fields 'dd','mm','yyyy' into
        # 'yyyy/mm/dd'
        selected_date = [ str(form.get('DTSTART_%s' % x))
                          for x in ('year', 'month', 'day') ]
        selected_date = '-'.join(selected_date)

        # Get event id
        uid = context.get_form_value('id')
        if uid is not None and '/' in uid:
            name, uid = uid.split('/', 1)

        # Get id and Record object
        properties = {}
        if uid is None:
            # Add user as Organizer
            organizer = str(context.user.get_abspath())
            properties['ORGANIZER'] = Property(organizer)
        else:
            event = resource.get_record(uid)
            if event is None:
                message = u'Cannot modify event, because it has been removed.'
                message = MSG(message)
                return context.come_back(message, goto=goto)
            # Test if current user is admin or organizer of this event
            if not resource.is_organizer_or_admin(context, event):
                message = u'You are not authorized to modify this event.'
                message = MSG(message)
                return context.come_back(message, goto, keep=True)

        for key in context.get_form_keys():
            if key in ('id', ';edit_event', 'resource'):
                continue
            # Get date and time for DTSTART and DTEND
            if key.startswith('DTSTART_day'):
                values = {}
                for real_key in ('DTSTART', 'DTEND'):
                    # Get date
                    v_date = [ str(form.get('%s_%s' % (real_key, x)))
                               for x in ('year', 'month', 'day') ]
                    v_date = '-'.join(v_date)
                    # Get time
                    hours = form.get('%s_hours' % real_key)
                    minutes = form.get('%s_minutes' % real_key)
                    params = {}
                    if hours is None:
                        value = v_date
                        params['VALUE'] = ['DATE']
                    else:
                        if minutes is None:
                            minutes = 0
                        v_time = '%s:%s' % (hours, minutes)
                        value = ' '.join([v_date, v_time])
                    # Get value as a datetime object
                    try:
                        value = DateTime.from_str(value)
                    except ValueError:
                        goto = ';edit_event?date=%s' % selected_date
                        message = u'One or more field is invalid.'
                        message = MSG(message)
                        return context.come_back(message, goto, keep=True)
                    values[real_key] = value, params
                # Check if start <= end
                if values['DTSTART'][0] > values['DTEND'][0]:
                    message = u'Start date MUST be earlier than end date.'
                    message = MSG(message)
                    goto = ';edit_event?date=%s' % \
                                             Date.encode(values['DTSTART'][0])
                    if uid is not None:
                        goto = goto + '&id=%s' % uid
                    elif 'timetable' in form:
                        timetable = form.get('timetable', '0')
                        goto = goto + '&timetable=%s' % timetable
                    return context.come_back(message, goto, keep=True)
                # Save values
                for key in ('DTSTART', 'DTEND'):
                    if key == 'DTEND' and 'VALUE' in values[key][1]:
                        value = values[key][0] + timedelta(days=1) - resolution
                        value = Property(value, values[key][1])
                    else:
                        value = Property(values[key][0], values[key][1])
                    properties[key] = value
            elif key.startswith('DTSTART') or key.startswith('DTEND'):
                continue
            else:
                datatype = resource.handler.get_datatype(key)
                multiple = getattr(datatype, 'multiple', False) is True
                if multiple:
                    datatype = Multiple(type=datatype)
                # Set
                values = form.get(key, [])
                if multiple:
                    properties[key] = [ Property(x) for x in values]
                else:
                    if values != []:
                        properties[key] = Property(values)

        if uid is not None:
            resource.update_record(uid, properties)
        else:
            resource.add_record('VEVENT', properties)

        goto = '%s?date=%s' % (goto, selected_date)
        message = MSG(u'Data updated')
        return context.come_back(message, goto=goto, keep=True)


    action_remove_event__access__ = 'is_allowed_to_edit'
    def action_remove_event(self, resource, context, form):
        method = context.get_cookie('method') or 'monthly_view'
        goto = ';%s?%s' % (method, date.today())
        if method not in dir(resource):
            goto = '../;%s?%s' % (method, date.today())
        # uid
        uid = context.get_form_value('id', default='')
        if '/' in uid:
            kk, uid = uid.split('/', 1)
        if uid =='':
            return context.come_back(None, goto)
        if resource.get_record(uid) is None:
            message = u'Cannot delete event, because it was already removed.'
            message = MSG(message)
            return context.come_back(message, goto=goto)

        resource._remove_event(uid)
        message = MSG(u'Event definitely deleted.')
        return context.come_back(message, goto=goto)


    action_cancel__access__ = 'is_allowed_to_edit'
    def action_cancel(self, resource, context, form):
        goto = ';%s' % context.get_cookie('method') or 'monthly_view'
        return context.come_back(None, goto)



class MonthlyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Monthly View')
    icon = 'icalendar.png'
    template = '/ui/ical/ical_monthly_view.xml'
    monthly_template = '/ui/ical/monthly_template.xml'


    def get_namespace(self, resource, context, ndays=7):
        today_date = date.today()

        # Current date
        c_date = context.get_form_value('date')
        c_date = get_current_date(c_date)
        # Save selected date
        context.set_cookie('selected_date', c_date)

        # Method
        method = context.get_cookie('method')
        if method != 'monthly_view':
            context.set_cookie('method', 'monthly_view')

        ###################################################################
        # Calculate start of previous week
        # 0 = Monday, ..., 6 = Sunday
        weekday = c_date.weekday()
        start = c_date - timedelta(7 + weekday)
        if self.get_first_day() == 0:
            start = start - timedelta(1)
        # Calculate last date to take in account as we display  5*7 = 35 days
        end = start + timedelta(35)

        ###################################################################
        # Get a list of events to display on view
        cal_indexes, events = resource.get_events_to_display(start, end)
        if isinstance(self.monthly_template, str):
            template = resource.get_resource(self.monthly_template)
        else:
            template = self.monthly_template

        ###################################################################
        namespace = {}
        # Add header to navigate into time
        namespace = self.add_selector_ns(c_date, 'monthly_view', namespace)
        # Get header line with days of the week
        namespace['days_of_week'] = self.days_of_week_ns(start, ndays=ndays)

        namespace['weeks'] = []
        day = start
        # 5 weeks
        for w in range(5):
            ns_week = {'days': [], 'month': u''}
            # 7 days a week
            for d in range(7):
                # day in timetable
                if d < ndays:
                    ns_day = {}
                    ns_day['nday'] = day.day
                    ns_day['selected'] = (day == today_date)
                    ns_day['url'] = resource.get_action_url(day=day)
                    # Insert events
                    ns_events, events = self.events_to_namespace(resource,
                        events, day, cal_indexes)
                    ns_day['events'] = stl(template, {'events': ns_events})
                    ns_week['days'].append(ns_day)
                    if day.day == 1:
                        month = months[day.month].gettext()
                        ns_week['month'] = month
                day = day + timedelta(1)
            namespace['weeks'].append(ns_week)

        namespace['add_icon'] = '/ui/images/button_add.png'
        return namespace



class WeeklyView(CalendarView):

    access = 'is_allowed_to_view'
    title = MSG(u'Weekly View')
    icon = 'icalendar.png'
    template = '/ui/ical/ical_grid_weekly_view.xml'


    def get_weekly_templates(self):
        """Get weekly templates to display events with timetables, and full
        day events.
        """
        return None, None


    # Get timetables as a list of string containing time start of each one
    def get_timetables_grid_ns(self, resource, start_date):
        """Build namespace to give as grid to gridlayout factory.
        """
        ns_timetables = []
        for calendar in resource.get_calendars():
            for start, end in calendar.get_timetables():
                for value in (start, end):
                    value = Time.encode(value)
                    if value not in ns_timetables:
                        ns_timetables.append(value)
        return ns_timetables


    def get_grid_events(self, resource, start_date, ndays=7, headers=None,
                        step=timedelta(1)):
        """Build namespace to give as data to gridlayout factory.
        """
        # Get events by day
        ns_days = []
        current_date = start_date

        if headers is None:
            headers = [None] * ndays

        # For each found calendar (or self), get events
        events = []
        # Get a list of events to display on view
        end = start_date + timedelta(days=ndays)
        cal_indexes, events = resource.get_events_to_display(start_date, end)
        for header in headers:
            ns_day = {}
            # Add header if given
            ns_day['header'] = header
            # Insert events
            ns_events, events = self.events_to_namespace(resource, events,
                                current_date, cal_indexes, grid=True)
            ns_day['events'] = ns_events
            ns_days.append(ns_day)
            current_date = current_date + step

        return ns_days


    def get_namespace(self, resource, context, ndays=7):
        # Current date
        c_date = context.get_form_value('date')
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

        namespace = {}
        # Add header to navigate into time
        namespace = self.add_selector_ns(c_date, 'weekly_view' ,namespace)

        # Get icon to appear to add a new event
        namespace['add_icon'] = '/ui/images/button_add.png'

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
        with_new_url = self.get_with_new_url()
        timetable = get_grid_data(events, timetables, start, templates,
                                  with_new_url)
        namespace['timetable_data'] = timetable

        return namespace



class CalendarUpload(FileUpload):

    title = MSG(u'Upload from an ical file')


    def action(self, resource, context, form):
        file = form['file']
        filename, mimetype, body = file

##        # Check wether the handler is able to deal with the uploaded file
        handler = resource.handler
##        if mimetype != handler.get_mimetype():
##            context.message = u'Unexpected file of mimetype %s' % mimetype
##            return

        # Replace
        try:
            handler.load_state_from_ical_file(StringIO(body))
        except:
            context.message = u'Failed to load the file, may contain errors.'
        else:
            context.server.change_object(resource)
            context.message = u'Version uploaded'



class DownloadView(FileView):

    title = MSG(u'Export in ical format')

##    XXX Check header is correct
##    def download(self, context):
##        response = context.response
##        response.set_header('Content-Type', 'text/calendar')
##        return self.handler.to_ical()


