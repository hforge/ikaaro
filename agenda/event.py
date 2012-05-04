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
from itools.database import register_field
from itools.datatypes import Date, DateTime, Enumerate, Time
from itools.gettext import MSG
from itools.web import ERROR, FormError, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.buttons import Remove_Button
from ikaaro.config_models import Model
from ikaaro.content import Content
from ikaaro.datatypes import DaysOfWeek
from ikaaro.emails import send_email
from ikaaro.fields import Boolean_Field, Char_Field, Select_Field
from ikaaro.fields import Date_Field, Datetime_Field, Owner_Field
from ikaaro.fields import SelectDays_Field
from ikaaro.utils import CMSTemplate, close_fancybox
from ikaaro.widgets import CheckboxWidget
from ikaaro import messages

# Import from calendar
from calendars import Calendars_Enumerate
from recurrence import RRule_Field, RRuleInterval_Field, RRuleUntil_Field
from recurrence import get_dates
from reminders import Reminder_Field


class Status(Enumerate):

    default = 'TENTATIVE'

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class AllDayWidget(CheckboxWidget):

    template = '/ui/agenda/widgets/allday.xml'


    def checked(self):
        return self.value in [True, 1, '1']



class AllDay_Field(Boolean_Field):

    widget = AllDayWidget
    title = MSG(u'All day')



class Event_Edit(AutoEdit):

    styles = ['/ui/agenda/style.css']
    can_be_open_in_fancybox = True

    # Fields
    fields = AutoEdit.fields + [
        'calendar',
        'dtstart', 'dtend', 'allday',
        'place', 'status',
        'rrule', 'rrule_interval', 'rrule_byday', 'rrule_until',
        'reminder']
    allday = AllDay_Field
    rrule_interval = RRuleInterval_Field
    rrule_byday = SelectDays_Field(title=MSG(u'On'), multiple=True)
    rrule_until = RRuleUntil_Field


    def get_actions(self, resource, context):
        actions = AutoEdit.actions

        # Singleton
        if not resource.get_value('rrule'):
            return actions + [Remove_Button]

        # Recurrent
        date = context.get_query_value('date', Date)
        if not date:
            return actions + [Remove_Button]

        date = context.format_date(date)
        return actions + [
            Remove_Button(title=MSG(u'Remove event at {date}', date=date),
                          name='remove_one_instance'),
            Remove_Button(title=MSG(u'Remove all events in the series'))]


    def get_scripts(self, context):
        scripts = super(Event_Edit, self).get_scripts(context)
        scripts.append('/ui/agenda/javascript.js')
        return scripts


    def get_before_namespace(self, resource, context):
        # Set organizer infos in ${before}
        owner = resource.get_owner()
        owner = resource.get_resource(owner).get_title()
        owner_msg = MSG(u'<p id="event-owner">Created by <em>{owner}</em></p>')
        owner_msg = owner_msg.gettext(owner=owner).encode('utf-8')
        return XMLParser(owner_msg)


    def _get_form(self, resource, context):
        form = super(Event_Edit, self)._get_form(resource, context)

        dtstart = form['dtstart']
        dtend = form['dtend']
        allday = form.get('allday', False)
        if not allday and (not form['dtstart_time'] or not form['dtend_time']):
            msg = ERROR(u"You have to fill start and end time")
            raise FormError(msg)

        if dtstart > dtend:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def get_value(self, resource, context, name, datatype):
        if name == 'allday':
            dtstart = resource.get_value('dtstart')
            dtend = resource.get_value('dtend')
            if type(dtstart) is date and type(dtend) is date:
                return True
            return False
        proxy = super(Event_Edit, self)
        return proxy.get_value(resource, context, name, datatype)


    def set_value(self, resource, context, name, form):
        if name in ('rrule_interval', 'rrule_byday', 'rrule_until', 'allday'):
            return False
        elif name == 'rrule':
            value = form.get(name, None)
            if value:
                kw = {
                    'interval': form.get('rrule_interval', None),
                    'until': form.get('rrule_until', None)}
                byday = form.get('rrule_byday', None)
                if value == 'weekly' and byday:
                    kw['byday'] = [ DaysOfWeek.get_shortname(v)
                                    for v in byday ]
                resource.set_value(name, value, **kw)
                return False
        proxy = super(Event_Edit, self)
        return proxy.set_value(resource, context, name, form)


    def action(self, resource, context, form):
        super(Event_Edit, self).action(resource, context, form)
        resource.notify_subscribers(context)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED
        return close_fancybox(context)


    def action_remove(self, resource, context, form):
        container = resource.parent
        container.del_resource(resource.name)
        # Ok
        context.message = MSG(u'Resource removed')
        return close_fancybox(context, default=str(resource.abspath[:-1]))


    def action_remove_one_instance(self, resource, context, form):
        date = context.get_query_value('date', Date)
        resource.set_value('exdate', date)
        # Ok
        context.message = MSG(u'Instance removed')
        return close_fancybox(context)



class Event_NewInstance(AutoAdd):

    can_be_open_in_fancybox = True

    # Fields
    fields = ['title', 'description', 'cc_list', 'calendar',
              'dtstart', 'dtend', 'allday',
              'place', 'status',
              'rrule', 'rrule_interval', 'rrule_byday', 'rrule_until',
              'reminder']
    allday = AllDay_Field
    rrule_interval = RRuleInterval_Field
    rrule_byday = SelectDays_Field(title=MSG(u'On'), multiple=True)
    rrule_until = RRuleUntil_Field


    def get_scripts(self, context):
        scripts = super(Event_NewInstance, self).get_scripts(context)
        scripts.append('/ui/agenda/javascript.js')
        return scripts


    def get_value(self, resource, context, name, datatype):
        if name in ('dtstart', 'dtend'):
            return context.query[name] or date.today()

        proxy = super(Event_NewInstance, self)
        return proxy.get_value(resource, context, name, datatype)


    def _get_form(self, resource, context):
        form = super(Event_NewInstance, self)._get_form(resource, context)

        dtstart = form['dtstart']
        dtend = form['dtend']
        allday = form.get('allday', False)
        if not allday and (not form['dtstart_time'] or not form['dtend_time']):
            msg = ERROR(u"You have to fill start and end time")
            raise FormError(msg)

        if dtstart > dtend:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def set_value(self, resource, context, name, form):
        if name in ('rrule_interval', 'rrule_byday', 'rrule_until', 'allday'):
            return False
        if name == 'rrule':
            value = form.get(name, None)
            if value:
                kw = {
                    'interval': form.get('rrule_interval', None),
                    'until': form.get('rrule_until', None)}
                byday = form.get('rrule_byday', None)
                if value == 'weekly' and byday:
                    kw['byday'] = [ DaysOfWeek.get_shortname(v)
                                    for v in byday ]
                resource.set_value(name, value, **kw)
                return False

        proxy = super(Event_NewInstance, self)
        return proxy.set_value(resource, context, name, form)


    def get_container(self, resource, context, form):
        return resource


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
        goto = str(resource.get_pathto(child))
        if self.goto_parent_view:
            goto = './;%s' % self.goto_parent_view
        elif self.goto_view:
            goto = '%s/;%s' % (goto, self.goto_view)
        return context.come_back(self.msg_new_resource, goto=goto)



class Start_Field(Datetime_Field):

    datatype = DateTime(time_is_required=False)
    stored = True
    title = MSG(u'Start')
    required = True
    widget = Datetime_Field.widget(value_time_default=time(9, 0))


class End_Field(Datetime_Field):

    datatype = DateTime(time_is_required=False)
    stored = True
    title = MSG(u'End')
    required = True
    widget = Datetime_Field.widget(value_time_default=time(10, 0))


class Event_Render(CMSTemplate):

    template = '/ui/agenda/event_render.xml'

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
    owner = Owner_Field
    calendar = Select_Field(datatype=Calendars_Enumerate, required=True,
                            title=MSG(u'Calendar'), indexed=True)
    dtstart = Start_Field
    dtend = End_Field
    place = Char_Field(title=MSG(u'Where'))
    status = Select_Field(datatype=Status, title=MSG(u'State'))
    rrule = RRule_Field(title=MSG(u'Recurrence'))
    exdate = Date_Field(multiple=True)
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

        # Recurrence
        rrule = self.metadata.get_property('rrule')
        dates = get_dates(start, end, rrule)
        # Exclude dates
        exdate = self.get_value('exdate')
        dates.difference_update(exdate)
        # Ok
        return sorted(dates)


    def get_value(self, name, language=None):
        if name in ('rrule_interval', 'rrule_byday', 'rrule_until'):
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


    def get_catalog_values(self):
        values = super(Event, self).get_catalog_values()
        values['dates'] = self.get_dates()
        return values


    def next_time_event(self):
        reminder = self.get_value('reminder')
        if not reminder:
            return None, None

        # Get start time (if no time, start_time is midnight)
        start = self.get_value('dtstart')
        start_time = start.time() if type(start) is datetime else time(0)

        # Dates
        context = get_context()
        now = context.timestamp
        delta = timedelta(seconds=reminder)
        for date in self.get_dates():
            date = datetime.combine(date, start_time)
            reminder = context.fix_tzinfo(date - delta)
            if reminder > now:
                return reminder, date

        return None, None


    def time_event(self, payload):
        context = get_context()
        to_addr = self.get_resource(self.get_owner()).get_value('email')
        send_email('event-reminder', context, to_addr, event=self, date=payload)


    def get_ns_event(self, current_day, grid=False):
        abspath = str(self.abspath)
        ns = {
            'id': abspath,
            'link': abspath,
            'title': self.get_title(),
            'cal': 0,
            'color': self.get_color(),
            'current_day': current_day,
            'description': self.get_value('description'),
            'status': self.get_value('status') or 'cal_busy',
            'url': None}

        ###############################################################
        # URL
        context = get_context()
        view = self.get_view('edit')
        if context.is_access_allowed(self, view, context.user):
            ns['url'] = '%s/;edit?date=%s' % (abspath, current_day)

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
                    ns['TIME'] = value
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
        calendar = self.get_resource(self.get_value('calendar'))
        return calendar.get_value('color')


    # Views
    new_instance = Event_NewInstance
    edit = Event_Edit



class EventModel(Model):

    class_id = 'model-event'
    class_title = MSG(u'Event model')

    base_class = Event



# Register
register_field('dates', Date(indexed=True, multiple=True))
