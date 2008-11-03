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
from textwrap import wrap

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
from ikaaro.table import TableView
from ikaaro.views import CompositeForm


url_expr = compile('([fh]t?tps?://[\w.@/;?=&#\-%:]*)')
def indent(text):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 150 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    lines = []
    for line in text.splitlines():
        for line in wrap(line, 150, break_long_words=False):
            lines.append(line)
        else:
            if line is '':
                lines.append(line)
    text = '\n'.join(lines)
    # Links
    for segment in url_expr.split(text):
        if (segment.startswith('http://') or
            segment.startswith('https://') or
            segment.startswith('ftp://')):
            attributes = {(xhtml_uri, 'href'): segment}
            yield START_ELEMENT, (xhtml_uri, 'a', attributes), 1
            # Reduce too long URI
            if len(segment) > 70:
                segment = segment[:34] + '...' + segment[-33:]
            yield TEXT, segment, 1
            yield END_ELEMENT, (xhtml_uri, 'a'), 1
        else:
            yield TEXT, segment, 1



# Definition of the fields of the forms to add and edit an issue
issue_fields = {
    'title': String(mandatory=True),
    'product': String(mandatory=True),
    'module': String,
    'version': String,
    'type': String(mandatory=True),
    'state': String(mandatory=True),
    'priority': String,
    'assigned_to': String,
    'comment': String,
    'cc_add': String,
    'cc_list': String,
    'cc_remove': Boolean,
    'file': String}


class Issue_Edit(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Issue')
    icon = 'edit.png'
    template = '/ui/tracker/edit_issue.xml'

    schema = issue_fields


    def get_namespace(self, resource, context):
        # Set Style & JS
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

        # Local variables
        users = resource.get_resource('/users')
        record = resource.get_last_history_record()
        title = record.get_value('title')
        product = record.get_value('product')
        module = record.get_value('module')
        version = record.get_value('version')
        type = record.get_value('type')
        priority = record.get_value('priority')
        assigned_to = record.get_value('assigned_to')
        state = record.get_value('state')
        comment = record.get_value('comment')
        cc_list = list(record.get_value('cc_list') or ())
        file = record.get_value('file')

        # Build the namespace
        namespace = {}
        namespace['title'] = title
        # Reported by
        reported_by = resource.get_reported_by()
        namespace['reported_by'] = users.get_resource(reported_by).get_title()
        # Topics, Version, Priority, etc.
        get = resource.parent.get_resource
        namespace['products'] = get('products').get_options(product)
        namespace['modules'] = get('modules').get_options(module)
        namespace['versions'] = get('versions').get_options(version)
        namespace['types'] = get('types').get_options(type)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        namespace['states'] = get('states').get_options(state, sort=False)
        # Assign To
        namespace['users'] = resource.parent.get_members_namespace(
                                                        assigned_to)
        # Comments
        comments = []
        i = 0
        for record in resource.get_history_records():
            comment = record.comment
            file = record.file
            if not comment and not file:
                continue
            datetime = record.datetime
            # solid in case the user has been removed
            username = record.username
            user_title = username
            if users.has_resource(username):
                user_title = users.get_resource(username).get_title()
            i += 1
            comments.append({
                'number': i,
                'user': user_title,
                'datetime': format_datetime(datetime),
                'comment': indent(comment),
                'file': file})
        comments.reverse()
        namespace['comments'] = comments

        users = resource.parent.get_members_namespace(cc_list, False)
        cc_list = []
        cc_add = []
        for user in users:
            user_id = user['id']
            if user_id == reported_by:
                continue
            if user['is_selected']:
                user['is_selected'] = False
                cc_list.append(user)
            else:
                cc_add.append(user)
        namespace['cc_add'] = cc_add
        namespace['cc_list'] = cc_list
        namespace['cc_remove'] = None

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
        versions = resource.get_resource('../versions')
        types = resource.get_resource('../types')
        states = resource.get_resource('../states')
        modules = resource.get_resource('../modules')
        priorities = resource.get_resource('../priorities')
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
        namespace = {}
        namespace['number'] = resource.name
        rows = []
        i = 0
        for record in resource.get_history_records():
            datetime = record.get_value('datetime')
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
                      'datetime': format_datetime(datetime),
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
                    version = versions.handler.get_record(int(version))
                    if version:
                        row_ns['version'] = version.get_value('title')
            if type != previous_type:
                previous_type = type
                row_ns['type'] = ' '
                if type is not None:
                    type = types.handler.get_record(int(type))
                    if type is not None:
                        row_ns['type'] = type.get_value('title')
            if state != previous_state:
                previous_state = state
                row_ns['state'] = ' '
                if state is not None:
                    state = states.handler.get_record(int(state))
                    if state is not None:
                        row_ns['state'] = state.get_value('title')
            if module != previous_module:
                previous_module = module
                row_ns['module'] = ' '
                if module is not None:
                    module = modules.handler.get_record(int(module))
                    if module is not None:
                        row_ns['module'] = module.get_value('title')
            if priority != previous_priority:
                previous_priority = priority
                row_ns['priority'] = ' '
                if priority is not None:
                    priority = priorities.handler.get_record(int(priority))
                    if priority is not None:
                        row_ns['priority'] = priority.get_value('title')
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
                    value = root.get_user(cc).get_property('email')
                    new_values.append(value)
                if new_values:
                    row_ns['cc_list'] = u', '.join(new_values)
                else:
                    row_ns['cc_list'] = ' '

            rows.append(row_ns)

        rows.reverse()
        namespace['rows'] = rows

        return namespace



class Issue_ViewResources(TableView):

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
        return TableView.get_item_value(self, resource, context, item, column)


    def action_remove(self, resource, context, form):
        resource = resource.get_resources()
        TableView.action_remove(self, resource, context, form)



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
        resources = resource.get_resources()

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
            record = resources.handler.get_record(id)
            get_value = resources.handler.get_record_value
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
        timetables = resources.get_timetables()
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
        resources = resource.get_resources()
        resources.handler.add_record(record)
        # Ok
        context.message = MSG_CHANGES_SAVED


    def action_edit(self, resource, context, form):
        id = context.query['id']
        resource.get_resources()

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
        resources = resource.get_resources()
        resources.handler.update_record(id, **record)
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
        resources = resource.get_resources()
        views = [
            self.subviews[0].GET(resource, context),
            self.subviews[1].GET(resources, context) ]

        return {'views': views}
