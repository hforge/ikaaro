# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2009 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from datetime import date, datetime, time, timedelta

# Import from itools
from itools.core import is_prototype
from itools.database import register_field
from itools.datatypes import Boolean, Date, DateTime, Enumerate, Time
from itools.gettext import MSG
from itools.uri import get_reference
from itools.web import ERROR, FormError, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.autoform import SelectWidget
from ikaaro.config_models import Model
from ikaaro.content import Content
from ikaaro.enumerates import DaysOfWeek, IntegerRange
from ikaaro.fields import Char_Field, Datetime_Field, Select_Field
from ikaaro.fields import Field, Owner_Field, SelectDays_Field
from ikaaro.folder import Folder
from ikaaro.utils import CMSTemplate, make_stl_template
from ikaaro import messages

# Import from calendar
from family import Calendar_FamiliesEnumerate
from reminders import Reminder_Field


# Recurrence
MAX_DELTA = timedelta(3650) # we cannot index an infinite number of values

def next_day(x, delta=timedelta(1)):
    return x + delta

def next_working_day(x, working_days):
    x = next_day(x)
    if str(x.isoweekday()) in working_days:
        return x
    return next_working_day(x, working_days)

def next_week(x, delta=timedelta(7)):
    return x + delta

def next_month(x):
    year = x.year
    month = x.month + 1
    if month == 13:
        month = 1
        year = year + 1
    # FIXME handle invalid dates (like 31 April)
    return date(year, month, x.day)

def next_year(x):
    # FIXME handle 29 February
    return date(x.year + 1, x.month, x.day)


rrules = {
    'daily': next_day,
    'weekly': next_week,
    'on_working_days': next_working_day,
    'monthly': next_month,
    'yearly': next_year}



class Status(Enumerate):

    default = 'TENTATIVE'

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class RRuleIntervalDataType(IntegerRange):
    count = 31


class RRuleDataType(Enumerate):

    options = [
        {'name': 'daily', 'value': MSG(u'Daily')},
        {'name': 'weekly', 'value': MSG(u'Weekly')},
        {'name': 'on_working_days', 'value': MSG(u'On working days')},
        {'name': 'monthly', 'value': MSG(u'Monthly')},
        {'name': 'yearly', 'value': MSG(u'Yearly')}]


class RRuleWidget(SelectWidget):

    template = make_stl_template("""
    <select id="${id}" name="${name}" multiple="${multiple}" size="${size}"
      class="${css}" onchange="update_rrule_parameters();">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>
    <script>
     <![CDATA[
       $(document).ready(function(){
         update_rrule_parameters();
       });
     ]]>
    </script>""")


class RRule_Field(Select_Field):
    """Recurrence Rule
        - byday allowed on value 'weekly' only
        - default byday is MO,TU,WE,TH,FR,SA,SU
        - interval not allowed on value 'daily'
        - default interval is 1

        Examples:
            rrule;byday=MO,WE,FR;interval=1:weekly
            rrule;interval=2:monthly
    """
    datatype = RRuleDataType
    parameters_schema = {'interval': RRuleIntervalDataType,
                         'byday': DaysOfWeek(multiple=True)}
    widget = RRuleWidget


class RRuleInterval_Field(Select_Field):
    datatype = RRuleIntervalDataType
    has_empty_option = False



def get_goto(form, event):
    """Utility function used by the edit and new-instance forms.
    """
    referrer = form['referrer']
    if referrer:
        path = get_reference(referrer).path
        views = (';monthly_view', ';weekly_view', ';daily_view')
        if path and path[-1] in views:
            return referrer

    return None



class Event_Edit(AutoEdit):

    styles = ['/ui/calendar/style.css']
    scripts = ['/ui/calendar/javascript.js']

    # Fields
    fields = AutoEdit.fields + ['owner', 'family', 'dtstart', 'dtend',
        'status', 'rrule', 'rrule_interval', 'rrule_byday', 'reminder', 'uid']
    rrule_interval = RRuleInterval_Field(title=MSG(u'Every'))
    rrule_byday = SelectDays_Field(title=MSG(u'On'), multiple=True)


    def get_fields(self):
        resource = self.context.resource
        fields = super(Event_Edit, self).get_fields()
        for name in fields:
            field = self.get_field(resource, name)
            if field is None or not is_prototype(field, Field):
                field = resource.get_field(name)
            if field is not None and not field.readonly:
                yield name


    def get_namespace(self, resource, context):
        proxy = super(Event_Edit, self)
        namespace = proxy.get_namespace(resource, context)

        # Set organizer infos in ${before}
        owner = resource.get_owner()
        owner = resource.get_resource(owner).get_title()
        owner = MSG(u'<p id="event-owner">Created by <em>%s</em></p>' % owner)
        owner = owner.gettext().encode('utf-8')
        namespace['before'] = XMLParser(owner)

        return namespace


    def _get_form(self, resource, context):
        form = super(Event_Edit, self)._get_form(resource, context)

        dtstart = form['dtstart']
        dtend = form['dtend']
        if type(dtstart) is not type(dtend):
            msg = ERROR(u'Each time must be filled, or neither.')
            raise FormError(msg)

        if dtstart > dtend:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def set_value(self, resource, context, name, form):
        if name in ('rrule_interval', 'rrule_byday'):
            return False
        elif name == 'rrule':
            value = form.get(name, None)
            if value:
                interval = form.get('rrule_interval', None)
                byday = form.get('rrule_byday', None)
                kw = {}
                if value != 'working_days':
                    kw['interval'] = interval
                if value == 'weekly' and byday:
                    bydays = []
                    for v in byday:
                        bydays.append(DaysOfWeek.get_shortname(v))
                    kw['byday'] = bydays
                resource.set_value(name, value, **kw)
                return False
        proxy = super(Event_Edit, self)
        return proxy.set_value(resource, context, name, form)


    def action(self, resource, context, form):
        super(Event_Edit, self).action(resource, context, form)
        resource.notify_subscribers(context)
        # Ok
        goto = get_goto(form, resource)
        return context.come_back(messages.MSG_CHANGES_SAVED, goto=goto)



class Event_NewInstance(AutoAdd):

    scripts = ['/ui/calendar/javascript.js']
    # Fields
    fields = Content.fields + ['owner', 'family', 'dtstart', 'dtend', 'status',
        'rrule', 'rrule_interval', 'rrule_byday', 'reminder', 'uid']
    rrule_interval = RRuleInterval_Field(title=MSG(u'Every'))
    rrule_byday = SelectDays_Field(title=MSG(u'On'), multiple=True)


    def get_fields(self):
        cls = self._resource_class
        fields = super(Event_NewInstance, self).get_fields()
        for name in fields:
            field = self.get_field(name)
            if field is None or not is_prototype(field, Field):
                field = cls.get_field(name)
            if field is not None and not field.readonly:
                yield name


    def get_value(self, resource, context, name, datatype):
        if name in ('dtstart', 'dtend'):
            return context.query[name] or date.today()

        proxy = super(Event_NewInstance, self)
        return proxy.get_value(resource, context, name, datatype)


    def _get_form(self, resource, context):
        form = super(Event_NewInstance, self)._get_form(resource, context)

        dtstart = form['dtstart']
        dtend = form['dtend']
        if type(dtstart) is not type(dtend):
            msg = ERROR(u'Each time must be filled, or neither.')
            raise FormError(msg)

        if dtstart > dtend:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def set_value(self, resource, context, name, form):
        if name in ('rrule_interval', 'rrule_byday'):
            return False
        if name == 'rrule':
            value = form.get(name, None)
            if value:
                interval = form.get('rrule_interval', None)
                byday = form.get('rrule_byday', None)
                kw = {}
                if value != 'working_days':
                    kw['interval'] = interval
                if value == 'weekly' and byday:
                    bydays = []
                    for v in byday:
                        bydays.append(DaysOfWeek.get_shortname(v))
                    kw['byday'] = bydays
                resource.set_value(name, value, **kw)
                return False

        proxy = super(Event_NewInstance, self)
        return proxy.set_value(resource, context, name, form)


    def get_container(self, resource, context, form):
        # XXX Copied from blog/blog.py
        date = form['dtstart']
        names = ['%04d' % date.year, '%02d' % date.month]

        container = context.root
        for name in names:
            folder = container.get_resource(name, soft=True)
            if folder is None:
                folder = container.make_resource(name, Folder)
            container = folder

        return container


    def get_new_resource_name(self, form):
        return form['container'].make_resource_name()


    def action(self, resource, context, form):
        # 1. Make the resource
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return

        # 3. Notify the subscribers
        child.notify_subscribers(context)

        # Ok
        goto = get_goto(form, child)
        if goto is None:
            goto = str(child.abspath)
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class EventDatetime_Field(Datetime_Field):

    datatype = DateTime(time_is_required=False)
    stored = True



class Event_Render(CMSTemplate):

    template = '/ui/calendar/event_render.xml'

    event = None
    day = None
    grid = False

    def ns(self):
        return self.event.get_ns_event(self.day, self.grid)



class Event(Content):

    class_id = 'event'
    class_title = MSG(u'Event')
    class_description = MSG(u'Calendar event')
    class_icon16 = 'icons/16x16/event.png'
    class_icon48 = 'icons/48x48/event.png'
    class_views = ['edit', 'links', 'backlinks', 'edit_state', 'subscribe']

    # Render
    render = Event_Render

    # Fields
    fields = Content.fields + ['owner', 'family', 'dtstart', 'dtend', 'status',
                               'rrule', 'reminder', 'uid']
    owner = Owner_Field
    family = Select_Field(datatype=Calendar_FamiliesEnumerate, required=True,
                title=MSG(u'Calendar'), indexed=True)
    dtstart = EventDatetime_Field(required=True, title=MSG(u'Start'))
    dtend = EventDatetime_Field(required=True, title=MSG(u'End'))
    status = Select_Field(datatype=Status, title=MSG(u'State'))
    rrule = RRule_Field(title=MSG(u'Recurrence'))
    reminder = Reminder_Field(title=MSG(u'Reminder'))
    uid = Char_Field(readonly=True)


    def init_resource(self, **kw):
        super(Event, self).init_resource(**kw)

        # uid
        context = get_context()
        if 'uid' not in kw:
            uid = '%s@%s' % (self.abspath, context.uri.authority)
            self.set_value('uid', uid)


    def get_dates(self):
        start = self.get_value('dtstart')
        if type(start) is datetime:
            start = start.date()
        end = self.get_value('dtend')
        if type(end) is datetime:
            end = end.date()
        days = range((end - start).days + 1)

        dates = set()
        f = lambda date: dates.update([ date + timedelta(x) for x in days ])

        rrule = self.metadata.get_property('rrule')
        if rrule is not None:
            rrule_name = rrule.value
            rrule_interval = int(rrule.get_parameter('interval') or 1)
            rrule = rrules.get(rrule_name)
            if rrule_name == 'on_working_days':
                working_days = self.get_config_calendar().get_working_days()
            if rrule:
                top = max(start, date.today()) + MAX_DELTA
                while start < top:
                    interval = rrule_interval
                    f(start)
                    if rrule_name == 'on_working_days':
                        start = rrule(start, working_days)
                    else:
                        while interval > 0:
                            start = rrule(start)
                            interval -= 1

        else:
            f(start)

        return sorted(dates)


    def get_value(self, name, language=None):
        if name in ('rrule_interval', 'rrule_byday'):
            f_name, kk, param = name.partition('_')
            property = self.metadata.get_property(f_name, language=language)
            if property:
                value = property.get_parameter(param)
                if param == 'byday' and value is not None:
                    bydays = []
                    for v in value:
                        bydays.append(DaysOfWeek.get_name_by_shortname(v))
                    return bydays
                return value
        proxy = super(Event, self)
        return proxy.get_value(name, language)


    def get_reminders(self):
        reminder = self.get_value('reminder')
        if not reminder:
            return []
        reminders = []
        # Get start time
        dtstart = self.get_value('dtstart')
        if type(dtstart) is datetime:
            start_time = dtstart.time()
        else:
            # If no time, start_time is midnight
            start_time = time(0)
        # For every date (reccurences) we add a reminder
        for d in self.get_dates():
            d_time = datetime.combine(d, start_time)
            reminders.append(d_time - timedelta(seconds=reminder))
        return reminders


    def get_catalog_values(self):
        values = super(Event, self).get_catalog_values()
        values['is_event'] = True
        values['family'] = self.get_value('family')
        values['dates'] = self.get_dates()
        values['reminders'] = self.get_reminders()
        return values


    def get_ns_event(self, current_day, grid=False):
        context = get_context()
        ns = {'id': str(self.abspath),
              'link': context.get_link(self),
              'title': self.get_title(),
              'cal': 0,
              'color': self.get_color(),
              'current_day': current_day,
              'description': self.get_value('description'),
              'status': self.get_value('status') or 'cal_busy'}

        ###############################################################
        # URL
        context = get_context()
        user = context.user
        root = context.root
        if root.is_allowed_to_view(user, self):
            ns['url'] = '%s/;edit' % context.get_link(self)
        else:
            ns['url'] = None

        ###############################################################
        # Set dtstart and dtend values using '...' for events which
        # appear into more than one cell
        dtstart = self.get_value('dtstart')
        dtend = self.get_value('dtend')

        dtstart_type = type(dtstart)
        if dtstart_type is datetime:
            ns['start'] = Time.encode(dtstart.time())[:5]
        else:
            ns['start'] = '00:00'

        if type(dtend) is datetime:
            ns['end'] = Time.encode(dtend.time())[:5]
        else:
            ns['end'] = '23:59'

        ###############################################################
        # Time
        e_dtstart = dtstart
        e_dtend = dtend
        if type(dtstart) is datetime:
            e_dtstart = dtstart.date()
        if type(dtend) is datetime:
            e_dtend = dtend.date()

        # Does current event occurs on current date ?
        starts_on = e_dtstart == current_day
        ends_on = e_dtend == current_day
        out_on = (e_dtstart < current_day and e_dtend > current_day)
        ns['TIME'] = None
        if grid:
            # Neither a full day event nor a multiple days event
            if dtstart_type is datetime and dtstart.date() == dtend.date():
                if ns['start'] == ns['end']:
                    ns['TIME'] = ns['start']
                else:
                    ns['TIME'] = '%s - %s' % (ns['start'], ns['end'])
            else:
                ns['start'] = ns['end'] = None
        elif not out_on:
            if dtstart_type is datetime:
                value = ''
                if starts_on and ns['start'] != ns['end']:
                    value = ns['start']
                    if ends_on:
                        value = value + '-'
                    else:
                        value = value + '...'
                if ends_on and ns['start'] != ns['end']:
                    value = value + ns['end']
                    if not starts_on:
                        value = '...' + value
                if value:
                    ns['TIME'] = '(' + value + ')'
        return ns


    def get_message(self, context, language=None):
        # Subject
        title=self.get_title()
        subject = MSG(u'The event "{title}" has been modified')
        subject = subject.gettext(title=title, language=language)
        # Body
        message = MSG(u'DO NOT REPLY TO THIS EMAIL.\n\n'
                      u'The user "{last_author}" has made some modifications '
                      u'to the event "{title}".\n'
                      u'To view these modifications please visit:\n'
                      u'{resource_uri}\n')
        uri = context.get_link(self)
        uri = str(context.uri.resolve(uri))
        uri += '/;edit'
        last_author = self.get_value('last_author')
        last_author = context.root.get_user_title(last_author)
        body = message.gettext(last_author=last_author, resource_uri=uri,
                               title=title, language=language)

        # And return
        return subject, body


    def get_color(self):
        family = self.get_resource(self.get_value('family'))
        return family.get_value('color')


    def get_config_calendar(self):
        return self.get_resource('/config/calendar')


    # Views
    new_instance = Event_NewInstance()
    edit = Event_Edit()



class EventModel(Model):

    class_id = 'model-event'
    class_title = MSG(u'Event model')

    base_class = Event



# Register
register_field('dates', Date(indexed=True, multiple=True))
register_field('reminders', DateTime(indexed=True, multiple=True))
register_field('is_event', Boolean(indexed=True))
