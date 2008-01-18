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
from datetime import datetime
from re import split
from string import Template
from textwrap import wrap

# Import from itools
from itools.csv import parse, Table
from itools.catalog import IntegerField, KeywordField
from itools.datatypes import DateTime, FileName, Integer, String, Unicode, XML
from itools.datatypes import Boolean, Tokens
from itools.handlers import checkid
from itools.html import xhtml_uri
from itools.i18n import format_datetime
from itools.stl import stl
from itools import vfs
from itools.xml import XMLParser, START_ELEMENT, END_ELEMENT, TEXT
from itools.web import FormError

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.messages import *
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.utils import generate_name, get_file_parts



def indent(text):
    """Replace URLs by HTML links.  Wrap lines (with spaces) to 150 chars.
    """
    text = text.encode('utf-8')
    # Wrap
    lines = []
    for line in text.splitlines():
        for line in wrap(line, 150):
            lines.append(line)
    text = '\n'.join(lines)
    # Links
    for segment in split('(http://[\w./;#]*)', text):
        if segment.startswith('http://'):
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
    class_title = u'Issue'
    class_description = u'Issue'
    class_views = [
        ['edit_form'],
        ['browse_content?mode=list'],
        ['history']]


    @staticmethod
    def _make_object(cls, folder, name):
        Folder._make_object(cls, folder, name)
        folder.set_handler('%s/.history' % name, History())


    def get_catalog_fields(self):
       fields = Folder.get_catalog_fields(self) + \
                [ IntegerField('module'), IntegerField('version'),
                  IntegerField('type'), IntegerField('priority'),
                  KeywordField('assigned_to'),  IntegerField('state') ]
       return fields


    def get_catalog_values(self):
        document = Folder.get_catalog_values(self)
        for name in ('module', 'version', 'type', 'priority', 'assigned_to',
                     'state'):
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


    def _add_record(self, context):
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
            filename, mimetype, body = get_file_parts(file)
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
            user_title = self.gettext(u'ANONYMOUS')
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
        if context.object.class_id == 'tracker':
            uri = context.uri.resolve('%s/;edit_form' % self.name)
        else:
            uri = context.uri.resolve(';edit_form')
        body = '#%s %s %s\n\n' % (self.name, self.get_value('title'), str(uri))
        template = Template(self.gettext(u'The user $title did some changes.'))
        body += template.substitute(title=user_title)
        body += '\n\n'
        if file:
            filename = unicode(filename, 'utf-8')
            template = Template(self.gettext(u'  New Attachment: $filename'))
            body += template.substitute(filename=filename) + '\n'
        comment = context.get_form_value('comment', type=Unicode)
        if comment:
            body += self.gettext(u'Comment') + u'\n'
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
            template = self.gettext(u'$field: $old_value to $new_value')
        else:
            # New issue
            template = self.gettext(u'$field: $old_value$new_value')
        template = Template(template)
        # Modification of title
        last_title = self.get_value('title') or ''
        new_title = record['title']
        if last_title != new_title:
            field = self.gettext(u'Title')
            text = template.substitute(field=field, old_value=last_title,
                                       new_value=new_title)
            modifications.append(text)
        # List modifications
        for key in [(u'Module', 'module', 'modules'),
                    (u'Version', 'version', 'versions'),
                    (u'Type', 'type', 'types'),
                    (u'Priority', 'priority', 'priorities'),
                    (u'State', 'state', 'states')]:
            field, name, csv_name = key
            field = self.gettext(field)
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
            text = template.substitute(field=field, old_value=last_title,
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
            field = self.gettext(u'Assigned To')
            text = template.substitute(field=field, old_value=last_user,
                                       new_value=new_user)
            modifications.append(text)

        # Modifications of cc_list
        last_cc = list(self.get_value('cc_list') or ())
        new_cc = list(record['cc_list'])
        if last_cc != new_cc:
            last_values = []
            for cc in last_cc:
                value = root.get_user(cc).get_property('email')
                last_values.append(value)
            new_values = []
            for cc in new_cc:
                value = root.get_user(cc).get_property('email')
                new_values.append(value)
            field = self.gettext(u'CC')
            last_values = ', '.join(last_values)
            new_values = ', '.join(new_values)
            text = template.substitute(field=field, old_value=last_values,
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
        parent = self.parent
        tables = {'module': parent.get_object('modules'),
                  'version': parent.get_object('versions'),
                  'type': parent.get_object('types'),
                  'priority': parent.get_object('priorities'),
                  'state': parent.get_object('states')}
        infos = {'name': self.name,
                 'id': int(self.name),
                 'title': self.get_value('title')}
        for name in 'module', 'version', 'type', 'priority', 'state':
            value = self.get_value(name)
            if value is not None:
                record = tables[name].handler.get_record(int(value))
                infos[name] = record and record.title or None
            else:
                infos[name] = None

        assigned_to = self.get_value('assigned_to')
        # solid in case the user has been removed
        users = self.get_object('/users')
        if assigned_to and users.has_object(assigned_to):
                user = users.get_object(assigned_to)
                infos['assigned_to'] = user.get_title()
        else:
            infos['assigned_to'] = ''
        infos['comment'] = self.get_value('comment')
        infos['mtime'] = format_datetime(self.get_mtime())
        infos['mtime_sort'] = self.get_mtime()
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


    #######################################################################
    # User Interface
    #######################################################################
    edit_form__access__ = 'is_allowed_to_edit'
    edit_form__label__ = u'Edit'
    def edit_form(self, context):
        # Set Style & JS
        context.styles.append('/ui/tracker/tracker.css')
        context.scripts.append('/ui/tracker/tracker.js')

        # Local variables
        users = self.get_object('/users')
        record = self.get_last_history_record()
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
        namespace['number'] = self.name
        namespace['title'] = title
        # Reported by
        reported_by = self.get_reported_by()
        namespace['reported_by'] = users.get_object(reported_by).get_title()
        # Topics, Version, Priority, etc.
        get = self.parent.get_object
        namespace['modules'] = get('modules').get_options(module)
        namespace['versions'] = get('versions').get_options(version)
        namespace['types'] = get('types').get_options(type)
        namespace['priorities'] = get('priorities').get_options(priority,
            sort=False)
        namespace['states'] = get('states').get_options(state, sort=False)
        # Assign To
        namespace['users'] = self.parent.get_members_namespace(assigned_to)
        # Comments
        comments = []
        i = 0
        for record in self.get_history_records():
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

        users = self.parent.get_members_namespace(cc_list, False)
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

        handler = self.get_object('/ui/tracker/edit_issue.xml')
        return stl(handler, namespace)


    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context):
        # Check input data
        try:
            form = context.check_form_input(issue_fields)
        except FormError:
            return context.come_back(MSG_MISSING_OR_INVALID)
        # Edit
        self._add_record(context)
        # Change
        context.server.change_object(self)

        return context.come_back(MSG_CHANGES_SAVED)


    #######################################################################
    # User Interface / History
    history__access__ = 'is_allowed_to_view'
    history__label__ = u'History'
    def history(self, context):
        # Set Style
        context.styles.append('/ui/tracker/tracker.css')

        # Local variables
        users = self.get_object('/users')
        versions = self.get_object('../versions')
        types = self.get_object('../types')
        states = self.get_object('../states')
        modules = self.get_object('../modules')
        priorities = self.get_object('../priorities')
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
        namespace['number'] = self.name
        rows = []
        i = 0
        for record in self.get_history_records():
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
            comment = XML.encode(Unicode.encode(comment))
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
                if module is None:
                    row_ns['version'] = ' '
                else:
                    version = versions.handler.get_record(int(version))
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

        handler = self.get_object('/ui/tracker/issue_history.xml')
        return stl(handler, namespace)


    def get_size(self):
        # FIXME Used by the browse list view (size is indexed)
        return 0


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self):
        remove = ['id', 'owner', 'dc:language', 'ikaaro:user_theme',
                  # Issue used to be VersioningAware
                  'ikaaro:history']
        Folder.update_20071215(self, remove=remove)


    def update_20071216(self):
        """Change '.history' from CSV to Table.
        """
        columns = ['datetime', 'username', 'title', 'module', 'version',
                   'type', 'priority', 'assigned_to', 'state', 'comment',
                   'file']

        folder = self.handler
        csv = vfs.open('%s/.history' % folder.uri).read()

        table = History()
        for line in parse(csv, columns, History.schema):
            record = {}
            for index, key in enumerate(columns):
                record[key] = line[index]
            # Rename link to attached file
            filename = record['file']
            if filename:
                name, extension, language = FileName.decode(filename)
                name = checkid(name)
                if name != filename:
                    record['file'] = name

            table.add_record(record)

        # Replace
        folder.del_handler('.history')
        folder.set_handler('.history', table)


###########################################################################
# Register
###########################################################################
register_object_class(Issue)
