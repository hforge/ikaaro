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
from itools.csv import Property
from itools.datatypes import Date, DateTime, Enumerate, String, Time, Unicode
from itools.gettext import MSG
from itools.web import ERROR, FormError, get_context

# Import from ikaaro
from ikaaro.autoform import DatetimeWidget, MultilineWidget, ReadOnlyWidget
from ikaaro.autoform import SelectWidget, TextWidget, location_widget
from ikaaro.autoform import timestamp_widget, title_widget
from ikaaro.buttons import Button
from ikaaro.cc import Observable, UsersList
from ikaaro.datatypes import Multilingual
from ikaaro.file import File
from ikaaro import messages
from ikaaro.registry import get_resource_class
from ikaaro.resource_views import DBResource_Edit
from ikaaro.views_new import NewInstance
from calendar_views import resolution


class Status(Enumerate):

    default = 'TENTATIVE'

    options = [{'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
               {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
               {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]



class Event_Edit(DBResource_Edit):

    access = 'is_allowed_to_edit'
    styles = ['/ui/calendar/style.css']

    query_schema = merge_dicts(DBResource_Edit.query_schema,
                               start=Date, start_time=Time,
                               end=Date, end_time=Time)

    schema = merge_dicts(DBResource_Edit.schema,
                         description=Multilingual,
                         start=Date(mandatory=True),
                         start_time=Time,
                         end=Date(mandatory=True),
                         end_time=Time,
                         status=Status(mandatory=True))
    del schema['subject']

    widgets = freeze([
        timestamp_widget,
        title_widget,
        DatetimeWidget('start', title=MSG(u'Start'),
                       tip=MSG(u'To add an event lasting all day long,'
                               u' leave time fields empty.')),
        DatetimeWidget('end', title=MSG(u'End')),
        MultilineWidget('description', title=MSG(u'Description'), rows=3),
        SelectWidget('status', title=MSG(u'State'), has_empty_option=False),
        ])

    actions = [
        Button(access='is_owner_or_admin', name='edit', css='button-ok',
               title=MSG(u'Save')),
        Button(access='is_owner_or_admin', name='remove', css='button-delete',
               title=MSG(u'Definitely remove'),
               confirm=messages.MSG_DELETE_SELECTION)]


    def _get_query_fields(self, resource, context):
        # Insert time fields by hand
        proxy = super(Event_Edit, self)
        fields, to_keep = proxy._get_query_fields(resource, context)
        to_keep.add('start_time')
        to_keep.add('end_time')
        return fields, to_keep


    def get_namespace(self, resource, context):
        proxy = super(Event_Edit, self)
        namespace = proxy.get_namespace(resource, context)

        # Set organizer infos in ${before}
        owner = resource.get_owner()
        owner = get_context().root.get_user_title(owner)
        from itools.xml import XMLParser
        owner = MSG(u'<p id="event-owner">Created by <em>%s</em></p>' % owner)
        owner = owner.gettext().encode('utf-8')
        namespace['before'] = XMLParser(owner)

        return namespace


    def get_value(self, resource, context, name, datatype):
        proxy = super(Event_Edit, self)
        if name in ('start', 'end'):
            name = 'dt%s' % name
        elif name == 'start_time':
            value = proxy.get_value(resource, context, 'dtstart', DateTime)
            v_time = value.time()
            context.query[name] = v_time
            return v_time
        elif name == 'end_time':
            prop = resource.metadata.get_property('dtend')
            param_value  = prop.get_parameter('VALUE')
            if param_value and param_value == 'DATE':
                return None
            value = prop.value
            v_time = value.time()
            context.query[name] = v_time
            return v_time
        value = proxy.get_value(resource, context, name, datatype)
        return value


    def _get_form(self, resource, context):
        form = super(Event_Edit, self)._get_form(resource, context)

        if ((form['start_time'] is None and form['end_time'] is not None)
            or (form['start_time'] is not None and form['end_time'] is None)):
            msg = ERROR(u'Each time must be filled, or neither.')
            raise FormError(msg)

        # Start
        start_time = form['start_time'] or time(0, 0)
        start = datetime.combine(form['start'], start_time)
        form['start'] = start
        # End
        end_time = form['end_time'] or time(0, 0)
        end = datetime.combine(form['end'], end_time)
        if form['end_time'] is None:
            end = end + timedelta(days=1) - resolution
        form['end'] = end

        if start > end:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def set_value(self, resource, context, name, form):
        # set_value shared in resource with new_instance
        return resource.set_value(self, context, name, form)


    def action_edit(self, resource, context, form):
        super(Event_Edit, self).action(resource, context, form)

        # Send notifications
        resource.notify_subscribers(context)

        # Goto calendar to prevent from reloading event with empty time
        goto = context.get_link(resource.parent)
        return context.come_back(context.message, goto)


    def action_remove(self, resource, context, form):
        # Remove
        calendar = resource.parent
        calendar.del_resource(resource.name)

        # Ok
        method = context.get_cookie('method') or 'monthly_view'
        goto = '../;%s?%s' % (method, date.today())

        message = ERROR(u'Event definitely deleted.')
        return context.come_back(message, goto=goto)


    def action_cancel(self, resource, context, form):
        goto = ';%s' % context.get_cookie('method') or 'monthly_view'
        return context.come_back(None, goto)



class Event_NewInstance(NewInstance):

    query_schema = merge_dicts(NewInstance.query_schema,
                               start=Date, start_time=Time,
                               end=Date, end_time=Time)

    schema = merge_dicts(NewInstance.schema,
                         start=Date(mandatory=True),
                         start_time=Time,
                         end=Date(mandatory=True),
                         end_time=Time)

    widgets = freeze([
        ReadOnlyWidget('cls_description'),
        TextWidget('title', title=MSG(u'Title'), size=20),
        DatetimeWidget('start', title=MSG(u'Start'),
                       tip=MSG(u'To add an event lasting all day long,'
                               u' leave time fields empty.')),
        DatetimeWidget('end', title=MSG(u'End')),
        SelectWidget('cc_list', title=MSG(u'Subscribers'),
                     has_empty_option=False),
        location_widget(include_name=False)])


    def get_schema(self, resource, context):
        return merge_dicts(self.schema,
                           cc_list=UsersList(resource=resource, multiple=True))


    def get_new_resource_name(self, form):
        return form['container'].get_new_id()


    def get_value(self, resource, context, name, datatype):
        if name in ('start', 'end'):
            return context.query[name] or date.today()

        proxy = super(Event_NewInstance, self)
        return proxy.get_value(resource, context, name, datatype)


    def _get_form(self, resource, context):
        form = super(Event_NewInstance, self)._get_form(resource, context)

        if ((form['start_time'] is None and form['end_time'] is not None)
            or (form['start_time'] is not None and form['end_time'] is None)):
            msg = ERROR(u'Each time must be filled, or neither.')
            raise FormError(msg)

        # Start
        start_time = form['start_time'] or time(0, 0)
        start = datetime.combine(form['start'], start_time)
        form['start'] = context.fix_tzinfo(start)
        # End
        end_time = form['end_time'] or time(0, 0)
        end = datetime.combine(form['end'], end_time)
        if form['end_time'] is None:
            end = end + timedelta(days=1) - resolution
        form['end'] = context.fix_tzinfo(end)

        if start > end:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)

        return form


    def set_value(self, resource, context, name, form):
        # set start/end with time
        return resource.set_value(self, context, name, form)


    def action(self, resource, context, form):
        # Get the container
        container = form['container']
        # Make the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # Set properties
        language = container.get_edit_languages(context)[0]
        title = Property(form['title'], lang=language)
        child.metadata.set_property('title', title)

        # Set properties / start and end
        self.set_value(child, context, 'start', form)
        self.set_value(child, context, 'end', form)

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

    # TODO This comes from the iCal age, use something better
    parameters_schema = {'VALUE': String(multiple=False)}



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
        dtstart=EventDateTime(source='metadata', indexed=True, stored=True),
        dtend=EventDateTime(source='metadata', indexed=True, stored=True),
        status=Status(source='metadata'),
        location=Unicode(source='metadata'),
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
        start_value_type = 'DATE-TIME' # FIXME

        ns['start'] = Time.encode(dtstart.time())[:5]
        ns['end'] = Time.encode(dtend.time())[:5]
        ns['TIME'] = None
        if grid:
            # Neither a full day event nor a multiple days event
            if start_value_type != 'DATE' and dtstart.date() == dtend.date():
                ns['TIME'] = '%s - %s' % (ns['start'], ns['end'])
            else:
                ns['start'] = ns['end'] = None
        elif not out_on:
            if start_value_type != 'DATE':
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


    def set_value(self, view, context, name, form):
        # Set values with time part for Event_Edit and Event_NewInstance
        # Used only with (start, end) by Event_NewInstance
        if name in ('start', 'end'):
            dt = form[name]
            if form['%s_time' % name] is None:
                if name == 'end':
                    dt = datetime.combine(dt, time(0, 0))
                    dt = dt + timedelta(days=1) - resolution
                dt = context.fix_tzinfo(dt)
                dt = Property(dt, VALUE='DATE')
            else:
                dt = context.fix_tzinfo(dt)
                dt = Property(dt)
            self.set_property('dt%s' % name, dt)
            return False
        elif name in ('start_time', 'end_time'):
            return False
        proxy = super(Event_Edit, view)
        return proxy.set_value(self, context, name, form)


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
