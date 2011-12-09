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
from itools.datatypes import Boolean, Date, DateTime, Enumerate, Time
from itools.gettext import MSG
from itools.web import ERROR, FormError, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.autoform import RadioWidget
from ikaaro.config_models import Model
from ikaaro.content import Content
from ikaaro.enumerates import DaysOfWeek
from ikaaro.fields import Boolean_Field, Char_Field, Select_Field
from ikaaro.fields import Datetime_Field, Owner_Field, SelectDays_Field
from ikaaro.folder import Folder
from ikaaro.utils import CMSTemplate, make_stl_template
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



class AllDayWidget(RadioWidget):

    template = make_stl_template("""
      ${widget}
      <script>
         $(document).ready(function(){
          var old_value_dtstart_time;
          var old_value_dtend_time;
          var dtstart_time = $("input[name='dtstart_time']");
          var dtend_time = $("input[name='dtend_time']");
          var has_changed_value = 0;
          $("#${id}-1").click(function(){
            change_all_day();
          });
          $("#${id}-0").click(function(){
            change_all_day();
          });
          function change_all_day(){
            if($("input:radio[name=${name}]:checked").val() == '1'){
              old_value_dtstart_time = dtstart_time.val();
              old_value_dtend_time = dtend_time.val();
              has_changed_value = 1;
              dtstart_time.val('');
              dtend_time.val('');
              dtstart_time.hide();
              dtend_time.hide();
            }else{
              if (has_changed_value == 1){
                dtstart_time.val(old_value_dtstart_time);
                dtend_time.val(old_value_dtend_time);
              }
              dtstart_time.show();
              dtend_time.show();
            }
          }
          change_all_day();
         });
      </script>""")

    def widget(self):
        return RadioWidget(datatype=Boolean,
            value=self.value, id=self.id, name=self.name)



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


    def get_scripts(self, context):
        scripts = super(Event_Edit, self).get_scripts(context)
        scripts.append('/ui/agenda/javascript.js')
        return scripts


    def get_before_namespace(self, resource, context):
        # Set organizer infos in ${before}
        owner = resource.get_owner()
        owner = resource.get_resource(owner).get_title()
        owner = MSG(u'<p id="event-owner">Created by <em>%s</em></p>' % owner)
        owner = owner.gettext().encode('utf-8')
        return XMLParser(owner)


    def _get_form(self, resource, context):
        form = super(Event_Edit, self)._get_form(resource, context)

        dtstart = form['dtstart']
        dtend = form['dtend']
        if not form['allday'] and (not form['dtstart_time'] or
                                   not form['dtend_time']):
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
        if not form['allday'] and (not form['dtstart_time'] or
                                   not form['dtend_time']):
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
        goto = str(resource.get_pathto(child))
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class EventDatetime_Field(Datetime_Field):

    datatype = DateTime(time_is_required=False)
    stored = True



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
    dtstart = EventDatetime_Field(required=True, title=MSG(u'Start'))
    dtend = EventDatetime_Field(required=True, title=MSG(u'End'))
    place = Char_Field(title=MSG(u'Where'))
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

        rrule = self.metadata.get_property('rrule')

        return get_dates(start, end, rrule)


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


    def get_reminders(self, dates=None):
        reminder = self.get_value('reminder')
        if not reminder:
            return None

        # Get start time (if no time, start_time is midnight)
        start = self.get_value('dtstart')
        start_time = start.time() if type(start) is datetime else time(0)

        # Dates
        if dates is None:
            dates = self.get_dates()

        # For every date (reccurences) we add a reminder
        delta = timedelta(seconds=reminder)
        return [ datetime.combine(x, start_time) - delta for x in dates ]


    def get_catalog_values(self):
        values = super(Event, self).get_catalog_values()
        values['calendar'] = self.get_value('calendar')
        dates = self.get_dates()
        values['dates'] = dates
        values['reminders'] = self.get_reminders(dates)
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
        calendar = self.get_resource(self.get_value('calendar'))
        return calendar.get_value('color')


    def get_config_calendar(self):
        return self.get_resource('/config/agenda')


    # Views
    new_instance = Event_NewInstance
    edit = Event_Edit



class EventModel(Model):

    class_id = 'model-event'
    class_title = MSG(u'Event model')

    base_class = Event



# Register
register_field('dates', Date(indexed=True, multiple=True))
register_field('reminders', DateTime(stored=True, multiple=True))
