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
from itools.core import freeze, merge_dicts
from itools.datatypes import DateTime, Enumerate, Time, Unicode
from itools.gettext import MSG
from itools.web import ERROR, FormError, get_context
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.autoform import DatetimeWidget, SelectWidget
from ikaaro.cc import Observable, UsersList
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro import messages
from ikaaro.registry import get_resource_class
from calendar_views import resolution


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
    fields = ['title', 'dtstart', 'dtend', 'description', 'rrule', 'status']

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

    fields = ['title', 'dtstart', 'dtend', 'cc_list']

    def _get_datatype(self, resource, context, name):
        if name == 'cc_list':
            widget = SelectWidget('cc_list', has_empty_option=False,
                                  title=MSG(u'Subscribers'))
            return UsersList(resource=resource, multiple=True, widget=widget)

        proxy = super(Event_NewInstance, self)
        return proxy._get_datatype(resource, context, name)


    def get_container(self, resource, context, form):
        # XXX Copied from blog/blog.py
        date = form['dtstart']
        names = ['%04d' % date.year, '%02d' % date.month]

        container = context.site_root
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
        dtstart_time = form['dtstart_time']
        dtend_time = form['dtend_time']

        if ((dtstart_time is None and dtend_time is not None)
            or (dtstart_time is not None and dtend_time is None)):
            msg = ERROR(u'Each time must be filled, or neither.')
            raise FormError(msg)

        # Start
        dtstart_time = dtstart_time or time(0)
        dtstart = datetime.combine(form['dtstart'], dtstart_time)
        form['dtstart'] = context.fix_tzinfo(dtstart)
        # End
        dtend_time = dtend_time or time(0)
        dtend = datetime.combine(form['dtend'], dtend_time)
        if form['dtend_time'] is None:
            dtend = dtend + timedelta(days=1) - resolution
        form['dtend'] = context.fix_tzinfo(dtend)

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
        # Get the container
        container = form['container']
        # Make the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # Set properties
        self.set_value(child, context, 'title', form)
        self.set_value(child, context, 'dtstart', form)
        self.set_value(child, context, 'dtend', form)
        # Set properties / cc_list
        child.set_property('cc_list', tuple(form['cc_list']))

        # Notify the subscribers
        user = context.user
        if user:
            child.set_property('last_author', user.name)
        child.notify_subscribers(context)

        # Ok
        goto = str(resource.get_pathto(child))
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class EventDateTime(DateTime):

    source = 'metadata'
    indexed = True
    stored = True
    time_is_required = False
    widget = DatetimeWidget



class Event(File, Observable):

    class_id = 'event'
    class_title = MSG(u'Event')
    class_description = MSG(u'Calendar event')
    class_icon16 = 'icons/16x16/event.png'
    class_icon48 = 'icons/48x48/event.png'
    class_views = ['edit', 'links', 'backlinks', 'edit_state', 'subscribe']


    class_schema = merge_dicts(
        File.class_schema,
        Observable.class_schema,
        # Metadata
        dtstart=EventDateTime(title=MSG(u'Start')),
        dtend=EventDateTime(title=MSG(u'End')),
        status=Status(source='metadata', title=MSG(u'State')),
        rrule=RRuleDataType(source='metadata', title=MSG(u'Recurrence')),
        uid=Unicode(source='metadata'))


    def init_resource(self, body=None, filename=None, extension=None, **kw):
        if 'uid' not in kw:
            path =  self.get_abspath()
            context = get_context()
            authority = context.uri.authority
            uid = str(path) + '@%s' % authority
            kw['uid'] = uid
        File.init_resource(self, body=body, filename=filename,
                    extension=extension, **kw)


    def get_ns_event(self, day, resource_name=None, conflicts_list=freeze([]),
                     timetable=None, grid=False, starts_on=True, ends_on=True,
                     out_on=True):
        """Specify the namespace given on views to represent an event.

        day: date selected XXX not used for now
        conflicts_list: list of conflicting uids for current resource, [] if
            not used
        timetable: timetable index or None
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
            'description': self.get_property('description'),
            'ORGANIZER': self.get_owner()}

        ###############################################################
        # Set dtstart and dtend values using '...' for events which
        # appear into more than one cell
        dtstart = self.get_property('dtstart')
        dtend = self.get_property('dtend')

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
        if id in conflicts_list:
            ns['status'] = 'cal_conflict'
        else:
            ns['status'] = 'cal_busy'
            status = self.get_property('status')
            if status:
                ns['status'] = status

        if not resource_name:
            id = str(id)
        else:
            id = '%s/%s' % (resource_name, id)
        ns['id'] = id

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
        last_author = self.get_property('last_author')
        last_author = context.root.get_user_title(last_author)
        body = message.gettext(last_author=last_author, resource_uri=uri,
                               title=title, language=language)

        # And return
        return subject, body


    # Views
    new_instance = Event_NewInstance()
    edit = Event_Edit()
