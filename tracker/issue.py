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
from mimetypes import guess_type
from re import sub

# Import from itools
from itools.datatypes import DateTime, Integer, String, Unicode, XML
from itools.handlers import checkid, Table
from itools.i18n import format_datetime
from itools.stl import stl
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.messages import *
from ikaaro.registry import register_object_class, get_object_class
from ikaaro.utils import generate_name
from ikaaro.versioning import VersioningAware



# Definition of the fields of the forms to add and edit an issue
issue_fields = [('title', True), ('version', True), ('type', True),
    ('state', True), ('module', False), ('priority', False),
    ('assigned_to', False), ('comment', False), ('file', False)]


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
              'file': String}



class Issue(Folder, VersioningAware):

    class_id = 'issue'
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


    def get_document_types(self):
        return [File]


    def get_context_menu_base(self):
        # Show the actions of the tracker
        return self.parent


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
        # Files XXX
        file = context.get_form_value('file')
        if file is None:
            record['file'] = ''
        else:
            filename, mimetype, body = file
            # Upload
            # The mimetype sent by the browser can be minimalistic
            guessed = guess_type(filename)[0]
            if guessed is not None:
                mimetype = guessed
            # Find a non used name
            filename = checkid(filename)
            filename = generate_name(filename, self.get_names())
            record['file'] = filename
            # Set the handler
            cls = get_object_class(mimetype)
            handler = cls.class_handler(string=body)
            metadata = cls.build_metadata()
            self.handler.set_handler(filename, handler)
            self.handler.set_handler('%s.metadata' % filename, metadata)
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
        assigned_to = self.get_value('assigned_to')
        if assigned_to:
            to_addrs.add(assigned_to)
        if user.name in to_addrs:
            to_addrs.remove(user.name)
        # Notify / Subject
        tracker_title = self.parent.get_property('dc:title') or 'Tracker Issue'
        subject = '[%s #%s] %s' % (tracker_title, self.name, title)
        # Notify / Body
        if context.object.class_id == 'tracker':
            uri = context.uri.resolve('%s/;edit_form' % self.name)
        else:
            uri = context.uri.resolve(';edit_form')
        body = '#%s %s %s\n\n' % (self.name, self.get_value('title'), str(uri))
        body += self.gettext(u'The user %s did some changes.') % user_title
        body += '\n\n'
        if file:
            body += self.gettext(u'  New Attachment: %s') % filename + '\n'
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
            to_addr = users.get_object(to_addr)
            to_addr = to_addr.get_property('ikaaro:email')
            root.send_email(to_addr, subject, text=body)


    def get_diff_with(self, record, context):
        """Return a text with the diff between the last and new issue state
        """
        root = context.root
        modifications = []
        history = self.get_history()
        if history.get_n_records() > 0:
            # Edit issue
            template = self.gettext(u'%s: %s to %s')
        else:
            # New issue
            template = self.gettext(u'%s: %s%s')
        # Modification of title
        last_title = self.get_value('title') or ''
        new_title = record['title']
        if last_title != new_title:
            title = self.gettext(u'Title')
            modifications.append(template %(title, last_title, new_title))
        # List modifications
        for key in [(u'Module', 'module', 'modules'),
                    (u'Version', 'version', 'versions'),
                    (u'Type', 'type', 'types'),
                    (u'Priority', 'priority', 'priorities'),
                    (u'State', 'state', 'states')]:
            title, name, csv_name = key
            title = self.gettext(title)
            new_value = record[name]
            last_value = self.get_value(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = u''
            csv = self.parent.get_object(csv_name).handler
            if last_value:
                last_title = csv.get_record(last_value).title
            if new_value:
                new_title = csv.get_record(new_value).title
            text = template % (title, last_title, new_title)
            modifications.append(text)

        # Modifications of assigned_to
        last_user = self.get_value('assigned_to')
        new_user = record['assigned_to']
        if last_user and last_user!=new_user:
            last_user = root.get_user(last_user)
            if last_user:
                last_user = last_user.get_property('ikaaro:email')
            new_user = root.get_user(new_user).get_property('ikaaro:email')
            title = self.gettext(u'Assigned to')
            modifications.append(template  %(title, last_user, new_user))

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
        records = self.get_history_records()
        i = len(records) - 1
        while i >= 0:
            record = records[i]
            comment = record.comment
            if comment:
                return comment
            i -= 1
        return ''


    def has_text(self, text):
        if text in self.get_value('title').lower():
            return True
        return text in self.get_comment().lower()


    def indent(self, text):
        """Replace spaces at the beginning of a line by "&nbsp;".  Replace
        '\n' by <br>\n and URL by HTML links.  Fold lines (with spaces) to
        150c.
        """
        res = []
        text = text.encode('utf-8')
        text = XML.encode(text)
        for line in text.splitlines():
            sline = line.lstrip()
            indent = len(line) - len(sline)
            if indent:
                line = '&nbsp;' * indent + sline
            if len(line) < 150:
                line = sub('http://(.\S*)', r'<a href="http://\1">\1</a>', line)
                res.append(line)
            else:
                # Fold lines to 150c
                text = line.split()
                line = ''
                while text != []:
                    word = text.pop(0)
                    if len(word) + len(line) > 150:
                        line = sub('http://(.\S*)',
                                   r'<a href="http://\1">\1</a>', line)
                        res.append(line)
                        line = ''
                    line = line + word + ' '
                if line != '':
                    line = sub('http://(.\S*)', r'<a href="http://\1">\1</a>',
                               line)
                    res.append(line)
        return XMLParser('\n'.join(res))


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
        file = record.get_value('file')

        # Build the namespace
        namespace = {}
        namespace['number'] = self.name
        namespace['title'] = title
        # Reported by
        reported_by = self.get_reported_by()
        reported_by = users.get_object(reported_by)
        namespace['reported_by'] = reported_by.get_title()
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
                'comment': self.indent(comment),
                'file': file})
        comments.reverse()
        namespace['comments'] = comments

        handler = self.get_object('/ui/tracker/edit_issue.xml')
        return stl(handler, namespace)


    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context):
        # Check input data
        error = context.check_form_input(issue_fields)
        if error is not None:
            return context.come_back(error)
        # Edit
        self._add_record(context)

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

        # Build the namespace
        namespace = {}
        namespace['number'] = self.name
        rows = []
        i = 0
        for record in self.get_history_records():
            datetime = record.datetime
            username = record.username
            title = record.title
            module = record.module
            version = record.version
            type = record.type
            priority = record.priority
            assigned_to = record.assigned_to
            state = record.state
            comment = record.comment
            file = record.file
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

            rows.append(row_ns)

        rows.reverse()
        namespace['rows'] = rows

        handler = self.get_object('/ui/tracker/issue_history.xml')
        return stl(handler, namespace)


    def get_size(self):
        # FIXME Used by VersioningAware to define the size of the document
        # FIXME Used by the browse list view (size is indexed)
        return 0


###########################################################################
# Register
###########################################################################
register_object_class(Issue)
