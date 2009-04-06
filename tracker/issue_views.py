# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 Gautier Hayoun <gautier.hayoun@itaapy.com>
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
from datetime import date, datetime, time
from re import compile
from textwrap import TextWrapper

# Import from itools
from itools.datatypes import Boolean, Date, Integer, String, Unicode
from itools.datatypes import XMLContent
from itools.gettext import MSG
from itools.ical import Time
from itools.html import xhtml_uri
from itools.i18n import format_datetime
from itools.web import STLForm, STLView
from itools.xml import XMLParser, START_ELEMENT, END_ELEMENT, TEXT

# Import from ikaaro
from ikaaro.messages import MSG_CHANGES_SAVED
from ikaaro.table_views import Table_View
from ikaaro.views import CompositeForm
from ikaaro.views import ContextMenu

# Local import
from datatypes import get_issue_fields, UsersList


###########################################################################
# Utilities
###########################################################################
url_expr = compile('([fh]t?tps?://[\w;/?:@&=+$,.#\-%]*)')
class OurWrapper(TextWrapper):

    def _split(self, text):
        # Override default's '_split' method to define URLs as unbreakable,
        # and reduce URLs if needed.
        # XXX This is fragile, since it uses TextWrapper private API.

        # Keep a mapping from reduced URL to full URL
        self.urls_map = {}

        # Get the chunks
        chunks = []
        for segment in url_expr.split(text):
            starts = segment.startswith
            if starts('http://') or starts('https://') or starts('ftp://'):
                if len(segment) > 95:
                    # Reduce URL
                    url = segment
                    segment = segment[:46] + '...' + segment[-46:]
                    self.urls_map[segment] = url
                else:
                    self.urls_map[segment] = segment
                chunks.append(segment)
            else:
                chunks.extend(TextWrapper._split(self, segment))
        return chunks



def indent(text):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 95 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    buffer = []
    text_wrapper = OurWrapper(width=95)
    for line in text.splitlines():
        line = text_wrapper.fill(line) + '\n'
        for segment in url_expr.split(line):
            url = text_wrapper.urls_map.get(segment)
            if url is None:
                buffer.append(segment)
            else:
                if buffer:
                    yield TEXT, ''.join(buffer), 1
                    buffer = []
                # <a>...</a>
                attributes = {(None, 'href'): url}
                yield START_ELEMENT, (xhtml_uri, 'a', attributes), 1
                yield TEXT, segment, 1
                yield END_ELEMENT, (xhtml_uri, 'a'), 1
    if buffer:
        yield TEXT, ''.join(buffer), 1
        buffer = []



###########################################################################
# Menu
###########################################################################
class IssueTrackerMenu(ContextMenu):

    title = MSG(u'Tracker')

    def get_items(self, resource, context):
        items = [
            {'title': MSG(u'Search for issues'),
             'href': '%s/;search' % context.get_link(resource.parent)},
            {'title': MSG(u'Add a new issue'),
             'href': '%s/;add_issue' % context.get_link(resource.parent)}]
        return items



###########################################################################
# Views
###########################################################################
class Issue_Edit(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Issue')
    icon = 'edit.png'
    template = '/ui/tracker/edit_issue.xml'


    def get_schema(self, resource, context):
        return get_issue_fields(resource.parent)


    def get_value(self, resource, context, name, datatype):
        history = resource.get_history()
        record = history.get_record(-1)
        return  record.get_value(name)


    def get_namespace(self, resource, context):
        # Set Style & JS
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

        # Local variables
        users = resource.get_resource('/users')
        history = resource.get_history()
        record = history.get_record(-1)

        # Build the namespace
        namespace = self.build_namespace(resource, context)

        # Comments
        comments = []
        i = 0
        for record in resource.get_history_records():
            comment = record.comment
            file = record.file
            if not comment and not file:
                continue
            rdatetime = record.datetime
            # solid in case the user has been removed
            username = record.username
            user_title = username
            if users.has_resource(username):
                user_title = users.get_resource(username).get_title()
            i += 1
            comments.append({
                'number': i,
                'user': user_title,
                'datetime': format_datetime(rdatetime),
                'comment': indent(comment),
                'file': file})
        comments.reverse()
        namespace['comments'] = comments

        # cc_list / cc_add / cc_remove
        cc_list = record.get_value('cc_list') or ()
        namespace['cc_list']= {'name': 'cc_list',
                              'value': [],
                              'class': None}
        namespace['cc_add']= {'name': 'cc_add',
                              'value': [],
                              'class': None}
        cc_value = namespace['cc_list']['value']
        add_value = namespace['cc_add']['value']
        for user in UsersList(tracker=resource.parent).get_options():
            user['selected'] = False
            if user['name'] in cc_list:
                cc_value.append(user)
            else:
                add_value.append(user)
        namespace['cc_remove'] = None

        # Reported by
        reported_by = resource.get_reported_by()
        namespace['reported_by'] = users.get_resource(reported_by).get_title()

        # list_products
        tracker = resource.parent
        namespace['list_products'] = tracker.get_list_products_namespace()

        return namespace


    def action(self, resource, context, form):
        # Edit
        resource._add_record(context, form)
        # Change
        context.server.change_resource(resource)
        context.message = MSG_CHANGES_SAVED



class Issue_History(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'History')
    icon = 'history.png'
    template = '/ui/tracker/issue_history.xml'


    def get_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Local variables
        users = resource.get_resource('/users')
        tracker = resource.parent
        versions = tracker.get_resource('version').handler
        types = tracker.get_resource('type').handler
        states = tracker.get_resource('state').handler
        modules = tracker.get_resource('module').handler
        priorities = tracker.get_resource('priority').handler
        # Initial values
        previous_title = None
        previous_version = None
        previous_type = None
        previous_state = None
        previous_module = None
        previous_priority = None
        previous_assigned_to = None
        previous_cc_list = None

        # Build the namespace
        rows = []
        i = 0
        for record in resource.get_history_records():
            rdatetime = record.get_value('datetime')
            username = record.get_value('username')
            title = record.get_value('title')
            module = record.get_value('module')
            version = record.get_value('version')
            type = record.get_value('type')
            priority = record.get_value('priority')
            assigned_to = record.get_value('assigned_to')
            state = record.get_value('state')
            comment = record.get_value('comment')
            cc_list = record.get_value('cc_list') or ()
            file = record.get_value('file')
            # Solid in case the user has been removed
            user_exist = users.has_resource(username)
            usertitle = (user_exist and
                         users.get_resource(username).get_title() or username)
            comment = XMLContent.encode(Unicode.encode(comment))
            comment = XMLParser(comment.replace('\n', '<br />'))
            i += 1
            row_ns = {'number': i,
                      'user': usertitle,
                      'datetime': format_datetime(rdatetime),
                      'title': None,
                      'version': None,
                      'type': None,
                      'state': None,
                      'module': None,
                      'priority': None,
                      'assigned_to': None,
                      'comment': comment,
                      'cc_list': None,
                      'file': file}

            if title != previous_title:
                previous_title = title
                row_ns['title'] = title
            if version != previous_version:
                previous_version = version
                row_ns['version'] = ' '
                if module is not None:
                    version = versions.get_record(int(version))
                    if version:
                        value = versions.get_record_value(version, 'title')
                        row_ns['version'] = value
            if type != previous_type:
                previous_type = type
                row_ns['type'] = ' '
                if type is not None:
                    type = types.get_record(int(type))
                    if type is not None:
                        value = types.get_record_value(type, 'title')
                        row_ns['type'] = value
            if state != previous_state:
                previous_state = state
                row_ns['state'] = ' '
                if state is not None:
                    state = states.get_record(int(state))
                    if state is not None:
                        value = states.get_record_value(state, 'title')
                        row_ns['state'] = value
            if module != previous_module:
                previous_module = module
                row_ns['module'] = ' '
                if module is not None:
                    module = modules.get_record(int(module))
                    if module is not None:
                        value = modules.get_record_value(module, 'title')
                        row_ns['module'] = value
            if priority != previous_priority:
                previous_priority = priority
                row_ns['priority'] = ' '
                if priority is not None:
                    priority = priorities.get_record(int(priority))
                    if priority is not None:
                        value = priorities.get_record_value(priority, 'title')
                        row_ns['priority'] = value
            if assigned_to != previous_assigned_to:
                previous_assigned_to = assigned_to
                if assigned_to and users.has_resource(assigned_to):
                    assigned_to_user = users.get_resource(assigned_to)
                    row_ns['assigned_to'] = assigned_to_user.get_title()
                else:
                    row_ns['assigned_to'] = ' '
            if cc_list != previous_cc_list:
                root = context.root
                previous_cc_list = cc_list
                new_values = []
                for cc in cc_list:
                    user = root.get_user(cc)
                    if user:
                        new_values.append(user.get_property('email'))
                if new_values:
                    row_ns['cc_list'] = u', '.join(new_values)
                else:
                    row_ns['cc_list'] = ' '

            rows.append(row_ns)

        rows.reverse()

        # Ok
        return {'number': resource.name, 'rows': rows}



class Issue_ViewResources(Table_View):

    search_template = None

    batch_msg1 = MSG(u"There is 1 assignment.")
    batch_msg2 = MSG(u"There are ${n} assignments.")


    def get_items(self, resource, context):
        issue = context.resource
        return resource.handler.search(issue=issue.name)


    def get_item_value(self, resource, context, item, column):
        if column == 'id':
            id = item.id
            return id, ';edit_resources?id=%s' % id
        return Table_View.get_item_value(self, resource, context, item,
                                         column)


    def action_remove(self, resource, context, form):
        calendar = resource.get_calendar()
        Table_View.action_remove(self, calendar, context, form)



class Issue_AddEditResource(STLForm):

    access = 'is_allowed_to_edit'
    template = '/ui/tracker/edit_resource.xml'

    query_schema = {
        'id': Integer}

    schema = {
        'resource': String,
        'dtstart': Date(mandatory=True),
        'dtend': Date(mandatory=True),
        'tstart': Time(default=time(0, 0)),
        'tend': Time(default=time(0, 0)),
        'comment': Unicode}


    def get_namespace(self, resource, context):
        calendar = resource.get_calendar()

        # Add or Edit
        id = context.query['id']
        if id is None:
            # Add a new resource-issue
            action = ';edit_resources'
            user = None
            d_start = d_end = date.today()
            t_start = t_end = ''
            comment = u''
        else:
            # Edit a resource-issue
            action = ';edit_resources?id=%s' % id
            record = calendar.handler.get_record(id)
            get_value = calendar.handler.get_record_value
            user = get_value(record, 'resource')
            dtstart = get_value(record, 'dtstart')
            dtend = get_value(record, 'dtend')
            comment = get_value(record, 'comment')
            d_start, t_start = dtstart.date(), dtstart.time()
            d_end, t_end = dtend.date(), dtend.time()
            t_start = t_start.strftime('%H:%M')
            t_end = t_end.strftime('%H:%M')
            id = str(id)

        # Time select
        timetables = calendar.get_timetables()
        time_select = [
            {'name': index,
             'start': start.strftime('%H:%M'),
             'end': end.strftime('%H:%M')}
            for index, (start, end) in enumerate(timetables) ]

        # Ok
        return {
            'action': action,
            'id': id,
            'users': resource.parent.get_members_namespace(user),
            'd_start': d_start.strftime('%Y-%m-%d'),
            't_start': t_start,
            'd_end': d_end.strftime('%Y-%m-%d'),
            't_end': t_end,
            'time_select': time_select,
            'comment': comment}


    def action_add(self, resource, context, form):
        dtstart = datetime.combine(form['dtstart'], form['tstart'])
        dtend = datetime.combine(form['dtend'], form['tend'])
        record = {
            'issue': resource.name,
            'resource': form['resource'],
            'dtstart': dtstart,
            'dtend': dtend,
            'comment': form['comment']}

        # Change
        calendar = resource.get_calendar()
        calendar.handler.add_record(record)
        # Ok
        context.message = MSG_CHANGES_SAVED


    def action_edit(self, resource, context, form):
        id = context.query['id']

        # New record
        dtstart = datetime.combine(form['dtstart'], form['tstart'])
        dtend = datetime.combine(form['dtend'], form['tend'])
        record = {
            'issue': resource.name,
            'resource': form['resource'],
            'dtstart': dtstart,
            'dtend': dtend,
            'comment': form['comment']}

        # Change
        calendar = resource.get_calendar()
        calendar.handler.update_record(id, **record)
        # Ok
        context.message = MSG_CHANGES_SAVED



class Issue_EditResources(CompositeForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit resources')
    icon = 'edit.png'

    subviews = [
        Issue_AddEditResource(),
        Issue_ViewResources(),
    ]

    def get_namespace(self, resource, context):
        # Override so we can pass a different resource to Issue_ViewResources
        calendar = resource.get_calendar()
        views = [
            self.subviews[0].GET(resource, context),
            self.subviews[1].GET(calendar, context) ]

        return {'views': views}
