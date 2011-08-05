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
from datetime import date, datetime, timedelta

# Import from itools
from itools.database import register_field
from itools.datatypes import Boolean, Date, DateTime, Enumerate, Time
from itools.gettext import MSG
from itools.web import ERROR, FormError, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.config_models import register_model_base_class
from ikaaro.content import Content
from ikaaro.fields import Char_Field, Datetime_Field, Select_Field
from ikaaro.folder import Folder
from ikaaro import messages


# Recurrence
MAX_DELTA = timedelta(3650) # we cannot index an infinite number of values

def next_day(x, delta=timedelta(1)):
    return x + delta

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
    'monthly': next_month,
    'yearly': next_year}



class Status(Enumerate):

    default = 'TENTATIVE'

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class RRuleDataType(Enumerate):

    options = [
        {'name': 'daily', 'value': MSG(u'Daily')},
        {'name': 'weekly', 'value': MSG(u'Weekly')},
        {'name': 'monthly', 'value': MSG(u'Monthly')},
        {'name': 'yearly', 'value': MSG(u'Yearly')}]



class Event_Edit(AutoEdit):

    styles = ['/ui/calendar/style.css']

    def get_fields(self, resource):
        for name, field in resource.get_fields():
            if not field.readonly:
                yield name


    def get_namespace(self, resource, context):
        proxy = super(Event_Edit, self)
        namespace = proxy.get_namespace(resource, context)

        # Set organizer infos in ${before}
        owner = resource.get_owner()
        owner = get_context().root.get_user_title(owner)
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


    def action_edit(self, resource, context, form):
        super(Event_Edit, self).action(resource, context, form)
        resource.notify_subscribers(context)



class Event_NewInstance(AutoAdd):

    def get_fields(self, cls):
        for name, field in cls.get_fields():
            if not field.readonly:
                yield name


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
        if name in ('dtstart_time', 'dtend_time'):
            return False

        proxy = super(Event_NewInstance, self)
        return proxy.set_value(resource, context, name, form)


    def action(self, resource, context, form):
        # 1. Make the resource
        container = form['container']
        class_id = context.query['type']
        cls = context.database.get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # 2. Set properties
        for key in self.get_fields(cls):
            self.set_value(child, context, key, form)

        # 3. Notify the subscribers
        child.notify_subscribers(context)

        # Ok
        goto = form['referrer']
        views = ('/;monthly_view', '/;weekly_view', '/;daily_view')
        if not goto.endswith(views):
            goto = str(resource.get_pathto(child))
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)


class EventDatetime_Field(Datetime_Field):

    datatype = DateTime(time_is_required=False)
    stored = True



class Event(Content):

    class_id = 'event'
    class_title = MSG(u'Event')
    class_description = MSG(u'Calendar event')
    class_icon16 = 'icons/16x16/event.png'
    class_icon48 = 'icons/48x48/event.png'
    class_views = ['edit', 'links', 'backlinks', 'edit_state', 'subscribe']


    fields = Content.fields + ['owner', 'dtstart', 'dtend', 'status', 'rrule',
                               'uid']
    owner = Char_Field(readonly=True)
    dtstart = EventDatetime_Field(required=True, title=MSG(u'Start'))
    dtend = EventDatetime_Field(required=True, title=MSG(u'End'))
    status = Select_Field(datatype=Status, title=MSG(u'State'))
    rrule = Select_Field(datatype=RRuleDataType, title=MSG(u'Recurrence'))
    uid = Char_Field(readonly=True)


    def init_resource(self, **kw):
        super(Event, self).init_resource(**kw)

        # uid
        context = get_context()
        if 'uid' not in kw:
            uid = '%s@%s' % (self.abspath, context.uri.authority)
            self.set_value('uid', uid)

        # Set owner
        if context.user:
            self.set_value('owner', context.user.name)


    def get_owner(self):
        return self.get_value('owner')


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

        rrule = self.get_value('rrule')
        rrule = rrules.get(rrule)
        if rrule:
            top = max(start, date.today()) + MAX_DELTA
            while start < top:
                f(start)
                start = rrule(start)
        else:
            f(start)

        return sorted(dates)


    def get_catalog_values(self):
        values = super(Event, self).get_catalog_values()
        values['is_event'] = True
        values['dates'] = self.get_dates()
        return values


    def get_ns_event(self, conflicts_list, grid, starts_on, ends_on, out_on):
        """Specify the namespace given on views to represent an event.

        conflicts_list: list of conflicting uids for current resource, [] if
            not used
        grid: current calculated view uses gridlayout
        starts_on, ends_on and out_on are used to adjust display.

        By default, we get:

          start: HH:MM, end: HH:MM,
            TIME: (HH:MM-HH:MM) or TIME: (HH:MM...) or TIME: (...HH:MM)
          or
          start: None,  end: None, TIME: None

          summary: 'summary of the event'
          status: 'status' (class: cal_conflict, if id in conflicts_list)
          ORGANIZER: 'organizer of the event'
        """
        ns = {
            'title': self.get_title(),
            'description': self.get_value('description'),
            'ORGANIZER': self.get_owner()}

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

        ns['TIME'] = None
        if grid:
            # Neither a full day event nor a multiple days event
            if dtstart_type is datetime and dtstart.date() == dtend.date():
                ns['TIME'] = '%s - %s' % (ns['start'], ns['end'])
            else:
                ns['start'] = ns['end'] = None
        elif not out_on:
            if dtstart_type is datetime:
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

        ###############################################################
        # Set class for conflicting events or just from status value
        id = self.get_abspath()
        ns['id'] = str(id)

        if id in conflicts_list:
            ns['status'] = 'cal_conflict'
        else:
            ns['status'] = 'cal_busy'
            status = self.get_value('status')
            if status:
                ns['status'] = status

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


    # Views
    new_instance = Event_NewInstance()
    edit = Event_Edit()



# Register
register_field('dates', Date(indexed=True, multiple=True))
register_field('is_event', Boolean(indexed=True))
register_model_base_class(Event)
