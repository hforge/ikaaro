# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Luis Arturo Belmar-Letelier <luis@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from operator import itemgetter
from re import compile
from string import Template
from textwrap import wrap

# Import from itools
from itools.csv import parse, Table
from itools.datatypes import Date, DateTime, FileName, Integer, String, Time, Unicode
from itools.datatypes import Boolean, Tokens, XMLContent
from itools.gettext import MSG
from itools.handlers import checkid
from itools.html import xhtml_uri
from itools.i18n import format_datetime
from itools.stl import stl
from itools import vfs
from itools.xml import XMLParser, START_ELEMENT, END_ELEMENT, TEXT
from itools.web import FormError, STLForm, STLView
from itools.xapian import IntegerField, KeywordField

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.messages import *
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.utils import generate_name
from ikaaro import widgets


# Select widget with onchange attribute to update time values.
time_select_template = list(XMLParser("""
    <select name="${name}" id="${name}" multiple="${multiple}"
     onchange="update_time('${name}')">
      <option value=""></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select> """,
    { None: 'http://www.w3.org/1999/xhtml',
     'stl': 'http://xml.itools.org/namespaces/stl'}))

url_expr = compile('(https?://[\w./;?=&#\-%:]*)')
def indent(text):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 150 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    lines = []
    for line in text.splitlines():
        for line in wrap(line, 150):
            lines.append(line)
        else:
            if line is '':
                lines.append(line)
    text = '\n'.join(lines)
    # Links
    for segment in url_expr.split(text):
        if segment.startswith('http://') or segment.startswith('https://'):
            attributes = {(xhtml_uri, 'href'): segment}
            yield START_ELEMENT, (xhtml_uri, 'a', attributes), 1
            yield TEXT, segment, 1
            yield END_ELEMENT, (xhtml_uri, 'a'), 1
        else:
            yield TEXT, segment, 1



# Definition of the fields of the forms to add and edit an issue
issue_fields = {
    'title': String(mandatory=True),
    'version': String(mandatory=True),
    'type': String(mandatory=True),
    'state': String(mandatory=True),
    'module': String(),
    'priority': String(),
    'assigned_to': String(),
    'comment': String(),
    'cc_add': String(),
    'cc_list': String(),
    'cc_remove': Boolean(),
    'file': String()}


class EditIssueForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Edit Issue')
    tab_icon = 'edit.png'
    template = '/ui/tracker/edit_issue.xml'

    schema = issue_fields


    def get_namespace(self, resource, context):
        # Set Style & JS
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

        # Local variables
        users = resource.get_object('/users')
        record = resource.get_last_history_record()
        title = record.get_value('title')
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
        namespace['number'] = resource.name
        namespace['title'] = title
        # Reported by
        reported_by = resource.get_reported_by()
        namespace['reported_by'] = users.get_object(reported_by).get_title()
        # Topics, Version, Priority, etc.
        get = resource.parent.get_object
        namespace['modules'] = get('modules').get_options(module)
        namespace['versions'] = get('versions').get_options(version)
        namespace['types'] = get('types').get_options(type)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        namespace['states'] = get('states').get_options(state, sort=False)
        # Assign To
        namespace['users'] = resource.parent.get_members_namespace(assigned_to)
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
            if users.has_object(username):
                user_title = users.get_object(username).get_title()
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
        context.server.change_object(resource)
        context.message = MSG_CHANGES_SAVED



class EditResourcesForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Edit resources')
    tab_icon = 'edit.png'
    template = '/ui/tracker/edit_resources.xml'

    schema = {
        'resource': String,
        'dtstart': Date,
        'dtend': Date,
        'tstart': Time,
        'tend': Time,
        'comment': Unicode,
        }

    query_schema = {
        'resource': String,
        'dtstart': Date,
        'dtend': Date,
        'tstart': Time,
        'tend': Time,
        'time_select': String,
        'comment': Unicode,
        'sortorder': String(default='up'),
        'sortby': String(multiple=True, default=['dtend']),
        }


    def get_namespace(self, resource, context):
        query = context.query
        resource = query.get('resource') or ''
        dtstart = query.get('dtstart', date.today())
        dtend = query.get('dtend', date.today())
        tstart = query['tstart']
        tend = query['tend']
        time_select = query['time_select']
        comment = query['comment']

        namespace = {}
        # New assignment
        namespace['issue'] = {'number': resource.name,
                              'title': resource.get_title()}
        namespace['users'] = resource.parent.get_members_namespace(resource)
        namespace['dtstart'] = dtstart
        namespace['tstart'] = tstart
        namespace['dtend'] = dtend
        namespace['tend'] = tend
        namespace['comment'] = comment
        namespace['time_select'] = resource.get_time_select('time_select',
                                                            time_select)

        # Existent
        resources = resource.get_resources().handler
        records = resources.search(issue=resource.name)
        users = context.root.get_object('/users')
        ns_records = []
        for record in records:
            id = record.id
            resource = record.get_value('resource')
            resource = users.get_object(resource)
            ns_record = {}
            ns_record['id'] = (id, '../resources/;edit_record_form?id=%s' % id)
            ns_record['resource'] = resource.get_title()
            ns_record['dtstart'] = record.get_value('dtstart')
            ns_record['dtend'] = record.get_value('dtend')
            ns_record['comment'] = record.get_value('comment')
            ns_record['issue'] = record.get_value('issue')
            ns_records.append(ns_record)

        fields = [('id', u'id')]
        for widget in resources.form:
            fields.append((widget.name, getattr(widget, 'title', widget.name)))
        sortby = query['sortby']
        sortorder = query['sortorder']
        ns_records.sort(key=itemgetter(sortby[0]), reverse=(sortorder=='down'))
        namespace['table'] = widgets.table(fields, ns_records, [sortby],
            sortorder, actions=[], table_with_form=False)

        return namespace


    def action(self, resource, context, form):
        tstart = form['tstart'] or time(0,0)
        tend = form['tend'] or time(0,0)
        record = {}
        record['issue'] = resource.name
        record['resource'] = form['resource']
        record['dtstart'] = datetime.combine(form['dtstart'], tstart)
        record['dtend'] = datetime.combine(form['dtend'], tend)
        resources = resource.get_resources()
        resources.handler.add_record(record)
        context.message = MSG_CHANGES_SAVED



class HistoryForm(STLView):

    access = 'is_allowed_to_view'
    tab_label = MSG(u'History')
    tab_icon = 'history.png'
    template = '/ui/tracker/issue_history.xml'


    def get_namespace(self, resource, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Local variables
        users = resource.get_object('/users')
        versions = resource.get_object('../versions')
        types = resource.get_object('../types')
        states = resource.get_object('../states')
        modules = resource.get_object('../modules')
        priorities = resource.get_object('../priorities')
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
            # solid in case the user has been removed
            user_exist = users.has_object(username)
            usertitle = (user_exist and
                         users.get_object(username).get_title() or username)
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
                if type is None:
                    row_ns['type'] = ' '
                else:
                    type = types.handler.get_record(int(type))
                    row_ns['type'] = type.get_value('title')
            if state != previous_state:
                previous_state = state
                if state is None:
                    row_ns['state'] = ' '
                else:
                    state = states.handler.get_record(int(state))
                    row_ns['state'] = state.get_value('title')
            if module != previous_module:
                previous_module = module
                if module is None:
                    row_ns['module'] = ' '
                else:
                    module = modules.handler.get_record(int(module))
                    row_ns['module'] = module.get_value('title')
            if priority != previous_priority:
                previous_priority = priority
                if priority is None:
                    row_ns['priority'] = ' '
                else:
                    priority = priorities.handler.get_record(int(priority))
                    row_ns['priority'] = priority.get_value('title')
            if assigned_to != previous_assigned_to:
                previous_assigned_to = assigned_to
                if assigned_to and users.has_object(assigned_to):
                    assigned_to_user = users.get_object(assigned_to)
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



class History(Table):

    schema = {'datetime': DateTime,
              'username': String,
              'title': Unicode,
              'module': Integer,
              'version': Integer,
              'type': Integer,
              'priority': Integer,
              'assigned_to': String,
              'state': Integer,
              'comment': Unicode,
              'cc_list': Tokens(),
              'file': String}



class Issue(Folder):

    class_id = 'issue'
    class_version = '20071216'
    class_title = MSG(u'Issue')
    class_description = MSG(u'Issue')
    class_views = ['edit', 'edit_resources', 'browse_content', 'history']


    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        folder.set_handler('%s/.history' % name, History())


    def get_catalog_fields(self):
       fields = Folder.get_catalog_fields(self) + \
                [ IntegerField('module'), IntegerField('version'),
                  IntegerField('type'), IntegerField('priority'),
                  KeywordField('assigned_to'),  IntegerField('state')]
       return fields


    def get_catalog_values(self):
        document = Folder.get_catalog_values(self)
        for name in ('module', 'version', 'type', 'priority', 'state'):
            document[name] = self.get_value(name)
        document['assigned_to'] = self.get_value('assigned_to') or 'nobody'
        return document


    def get_document_types(self):
        return [File]


    def get_context_menu_base(self):
        # Show the actions of the tracker
        return self.parent


    def get_mtime(self):
        """Return the datetime of the last record"""
        last_record = self.get_last_history_record()
        if last_record:
            return last_record.datetime
        return self.get_mtime()


    def get_links(self):
        base = str(self.abspath)

        links = []
        for record in self.get_history_records():
            filename = record.file
            if filename:
                links.append('%s/%s' % (base, filename))
        return links


    #######################################################################
    # API
    #######################################################################
    def get_title(self):
        return '#%s %s' % (self.name, self.get_value('title'))


    def get_resources(self):
        return self.parent.get_object('resources')


    def get_history(self):
        return self.handler.get_handler('.history', cls=History)


    def get_history_records(self):
        return self.get_history().get_records()


    def get_last_history_record(self):
        history = self.handler.get_handler('.history', cls=History)
        n_records = history.get_n_records()
        if n_records == 0:
            return None
        return history.get_record(n_records - 1)


    def get_value(self, name):
        record = self.get_last_history_record()
        if record:
            return record.get_value(name)
        return None


    def _add_record(self, context, form):
        user = context.user
        root = context.root
        parent = self.parent
        users = root.get_object('users')

        record = {}
        # Datetime
        record['datetime'] = datetime.now()
        # User XXX
        if user is None:
            record['username'] = ''
        else:
            record['username'] = user.name
        # Title
        title = context.get_form_value('title', type=Unicode).strip()
        record['title'] = title
        # Version, Priority, etc.
        for name in ['module', 'version', 'type', 'priority', 'assigned_to',
                     'state', 'comment']:
            type = History.schema[name]
            value = context.get_form_value(name, type=type)
            if type == Unicode:
                value = value.strip()
            record[name] = value
        # CCs
        cc_list = list(self.get_value('cc_list') or ())
        cc_remove = context.get_form_value('cc_remove')
        if cc_remove:
            cc_remove = context.get_form_values('cc_list')
            for cc in cc_remove:
                cc_list.remove(cc)
        cc_add = context.get_form_values('cc_add')
        if cc_add:
            cc_list.extend(cc_add)
        record['cc_list'] = cc_list

        # Files XXX
        file = context.get_form_value('file')
        if file is None:
            record['file'] = ''
        else:
            # Upload
            filename, mimetype, body = form['file']
            # Find a non used name
            name = checkid(filename)
            name, extension, language = FileName.decode(name)
            name = generate_name(name, self.get_names())
            # Add attachement
            cls = get_object_class(mimetype)
            cls.make_object(cls, self, name, body=body, filename=filename,
                            extension=extension, format=mimetype)
            # Link
            record['file'] = name
        # Update
        modifications = self.get_diff_with(record, context)
        history = self.get_history()
        history.add_record(record)
        # Send a Notification Email
        # Notify / From
        if user is None:
            user_title = MSG(u'ANONYMOUS')
        else:
            user_title = user.get_title()
        # Notify / To
        to_addrs = set()
        reported_by = self.get_reported_by()
        if reported_by:
            to_addrs.add(reported_by)
        for cc in cc_list:
            to_addrs.add(cc)
        assigned_to = self.get_value('assigned_to')
        if assigned_to:
            to_addrs.add(assigned_to)
        if user.name in to_addrs:
            to_addrs.remove(user.name)
        # Notify / Subject
        tracker_title = self.parent.get_property('title') or 'Tracker Issue'
        subject = '[%s #%s] %s' % (tracker_title, self.name, title)
        # Notify / Body
        if context.resource.class_id == 'tracker':
            uri = context.uri.resolve('%s/;edit' % self.name)
        else:
            uri = context.uri.resolve(';edit')
        body = '#%s %s %s\n\n' % (self.name, self.get_value('title'), str(uri))
        message = MSG(u'The user $title did some changes.')
        body +=  message.gettext(title=user_title)
        body += '\n\n'
        if file:
            filename = unicode(filename, 'utf-8')
            message = MSG(u'  New Attachment: $filename')
            message = message.gettext(filename=filename)
            body += message + '\n'
        comment = context.get_form_value('comment', type=Unicode)
        if comment:
            body += MSG(u'Comment').gettext() + u'\n'
            body += u'-------\n\n'
            body += comment + u'\n\n'
            body += u'-------\n\n'
        if modifications:
            body += modifications
        # Notify / Send
        for to_addr in to_addrs:
            to_addr = users.get_object(to_addr).get_property('email')
            root.send_email(to_addr, subject, text=body)


    def get_diff_with(self, record, context):
        """Return a text with the diff between the last and new issue state
        """
        root = context.root
        modifications = []
        history = self.get_history()
        if history.get_n_records() > 0:
            # Edit issue
            template = MSG(u'$field: $old_value to $new_value')
        else:
            # New issue
            template = MSG(u'$field: $old_value$new_value')
        # Modification of title
        last_title = self.get_value('title') or ''
        new_title = record['title']
        if last_title != new_title:
            field = MSG(u'Title').gettext()
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title)
            modifications.append(text)
        # List modifications
        for key in [(u'Module', 'module', 'modules'),
                    (u'Version', 'version', 'versions'),
                    (u'Type', 'type', 'types'),
                    (u'Priority', 'priority', 'priorities'),
                    (u'State', 'state', 'states')]:
            field, name, csv_name = key
            field = MSG(field).gettext()
            new_value = record[name]
            last_value = self.get_value(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = u''
            csv = self.parent.get_object(csv_name).handler
            if last_value or last_value == 0:
                last_title = csv.get_record(last_value).title
            if new_value or new_value == 0:
                new_title = csv.get_record(new_value).title
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title)
            modifications.append(text)

        # Modifications of assigned_to
        last_user = self.get_value('assigned_to') or ''
        new_user = record['assigned_to']
        if last_user != new_user:
            if last_user:
                last_user = root.get_user(last_user).get_property('email')
            if new_user:
                new_user = root.get_user(new_user).get_property('email')
            field = MSG(u'Assigned To')
            text = field.gettext(field=field, old_value=last_user,
                                 new_value=new_user)
            modifications.append(text)

        # Modifications of cc_list
        last_cc = list(self.get_value('cc_list') or ())
        new_cc = list(record['cc_list'] or ())
        if last_cc != new_cc:
            last_values = []
            for cc in last_cc:
                value = root.get_user(cc).get_property('email')
                last_values.append(value)
            new_values = []
            for cc in new_cc:
                value = root.get_user(cc).get_property('email')
                new_values.append(value)
            field = MSG(u'CC').gettext()
            last_values = ', '.join(last_values)
            new_values = ', '.join(new_values)
            text = template.gettext(field=field, old_value=last_values,
                                    new_value=new_values)
            modifications.append(text)

        return u'\n'.join(modifications)


    def get_reported_by(self):
        history = self.get_history()
        return history.get_record(0).username


    def get_informations(self):
        """Construct a dict with issue informations.  This dict is used to
        construct a line for a table.
        """
        # Build the namespace
        get_value = self.get_last_history_record().get_value
        infos = {
            'name': self.name,
            'id': int(self.name),
            'title': get_value('title'),
            'comment': get_value('comment'),
            'rank': None,
            }

        # Select Tables
        get_object = self.parent.get_object
        tables = {'module': 'modules', 'version': 'versions', 'type': 'types',
                  'priority': 'priorities', 'state': 'states'}

        for name in ('module', 'version', 'type', 'priority', 'state'):
            value = get_value(name)
            if value is None:
                infos[name] = None
                infos['%s_rank'% name] = None
            else:
                record = get_object(tables[name]).handler.get_record(value)
                infos[name] = record and record.title or None
                if name in ('priority', 'state'):
                    infos['%s_rank'% name] = record.get_value('rank')

        # Assigned-To
        assigned_to = get_value('assigned_to')
        infos['assigned_to'] = ''
        if assigned_to:
            users = self.get_object('/users')
            if users.has_object(assigned_to):
                user = users.get_object(assigned_to)
                infos['assigned_to'] = user.get_title()

        # Modification Time
        mtime = self.get_mtime()
        infos['mtime'] = format_datetime(mtime)
        infos['mtime_sort'] = mtime

        return infos


    def get_comment(self):
        records = list(self.get_history_records())
        i = len(records) - 1
        while i >= 0:
            record = records[i]
            comment = record.comment
            if comment:
                return comment
            i -= 1
        return ''


    def to_text(self):
        records = list(self.get_history_records())
        comments = [ r.comment for r in records
                     if r.comment ]
        return u'\n'.join(comments)


    def has_text(self, text):
        if text in self.get_value('title').lower():
            return True
        return text in self.get_comment().lower()


    def get_time_select(self, name, value):
        timetables = self.get_resources().get_timetables()
        options = []
        for index, (tstart, tend) in enumerate(timetables):
            opt = '%s - %s' % (tstart.strftime('%H:%M'), tend.strftime('%H:%M'))
            options.append(
                {'name': index, 'value': opt, 'selected': index == value})
        namespace = {'name': name, 'multiple': False, 'options': options}

        return stl(events=time_select_template, namespace=namespace)


    def get_size(self):
        # FIXME Used by the browse list view (size is indexed)
        return 0


    #######################################################################
    # User Interface
    #######################################################################
    edit = EditIssueForm()
    edit_resources = EditResourcesForm()
    history = HistoryForm()




###########################################################################
# Register
###########################################################################
register_object_class(Issue)
