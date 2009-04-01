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
from datetime import datetime
from string import Template

# Import from itools
from itools.csv import Table
from itools.datatypes import DateTime, Integer, String, Unicode, Tokens
from itools.gettext import MSG
from itools.handlers import checkid
from itools.vfs import FileName
from itools.xapian import IntegerField, KeywordField
from itools.web import get_context

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.registry import register_resource_class, get_resource_class
from ikaaro.utils import generate_name
from issue_views import Issue_Edit, Issue_EditResources, Issue_History
from issue_views import IssueTrackerMenu


class History(Table):

    record_schema = {
        'datetime': DateTime,
        'username': String,
        'title': Unicode,
        'product': Integer,
        'module': Integer,
        'version': Integer,
        'type': Integer,
        'state': Integer,
        'priority': Integer,
        'assigned_to': String,
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
    def _make_resource(cls, folder, name):
        Folder._make_resource(cls, folder, name)
        folder.set_handler('%s/.history' % name, History())


    def get_catalog_fields(self):
        fields = Folder.get_catalog_fields(self)
        # Metadata
        names = [
            'id', 'product', 'module', 'version', 'type', 'state', 'priority']
        for name in names:
            field = IntegerField(name, is_stored=True)
            fields.append(field)
        # Assign To
        field = KeywordField('assigned_to', is_stored=True)
        fields.append(field)
        # Ok
        return fields


    def get_catalog_values(self):
        document = Folder.get_catalog_values(self)
        document['id'] = int(self.name)
        names = 'product', 'module', 'version', 'type', 'priority', 'state'
        for name in names:
            document[name] = self.get_value(name)
        document['assigned_to'] = self.get_value('assigned_to') or 'nobody'
        document['title'] = self.get_value('title')
        return document


    def get_document_types(self):
        return [File]


    def get_mtime(self):
        """Return the datetime of the last record.
        """
        history = self.get_history()
        record = history.get_record(-1)
        if record:
            return history.get_record_value(record, 'datetime')
        return self.get_mtime()


    def get_links(self):
        base = self.get_abspath()

        links = []
        for record in self.get_history_records():
            filename = record.file
            if filename:
                links.append(str(base.resolve2(filename)))
        return links


    def change_link(self, old_path, new_path):
        base = self.get_abspath()
        old_name = base.get_pathto(old_path)
        history = self.get_history()
        for record in history.get_records():
            file = history.get_record_value(record, 'file')
            if file == old_name:
                value = str(base.get_pathto(new_path))
                history.update_record(record.id, **{'file': value})
        # Reindex
        get_context().server.change_resource(self)


    #######################################################################
    # API
    #######################################################################
    def get_title(self, language=None):
        return '#%s %s' % (self.name, self.get_value('title'))


    def get_calendar(self):
        return self.parent.get_resource('calendar')


    def load_handlers(self):
        Folder.load_handlers(self)
        self.get_history()


    def get_history(self):
        return self.handler.get_handler('.history', cls=History)


    def get_history_records(self):
        return self.get_history().get_records()


    def get_value(self, name):
        history = self.get_history()
        record = history.get_record(-1)
        if record:
            return history.get_record_value(record, name)
        return None


    def _add_record(self, context, form):
        user = context.user
        root = context.root
        parent = self.parent
        users = root.get_resource('users')

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
        for name in ['product', 'module', 'version', 'type', 'state',
                     'priority', 'assigned_to', 'comment']:
            type = History.record_schema[name]
            value = context.get_form_value(name, type=type)
            if type == Unicode:
                value = value.strip()
            record[name] = value
        # CCs
        cc_list = set(self.get_value('cc_list') or ())
        cc_remove = context.get_form_value('cc_remove')
        if cc_remove:
            cc_remove = context.get_form_values('cc_list')
            cc_list = cc_list.difference(cc_remove)
        cc_add = context.get_form_values('cc_add')
        if cc_add:
            cc_list = cc_list.union(cc_add)
        record['cc_list'] = list(cc_list)

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
            cls = get_resource_class(mimetype)
            cls.make_resource(cls, self, name, body=body, filename=filename,
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
        body = '#%s %s %s\n\n' % (self.name, self.get_value('title'),
                                  str(uri))
        message = MSG(u'The user $title did some changes.')
        body +=  message.gettext(title=user_title)
        body += '\n\n'
        if file:
            filename = unicode(filename, 'utf-8')
            message = MSG(u'New Attachment: $filename')
            message = message.gettext(filename=filename)
            body += message + '\n'
        comment = context.get_form_value('comment', type=Unicode)
        if modifications:
            body += modifications
            body += '\n\n'
        if comment:
            title = MSG(u'Comment').gettext()
            separator = len(title) * u'-'
            template = u'${title}\n${separator}\n\n${comment}\n'
            template = Template(template)
            body += template.substitute(title=title, separator=separator,
                                        comment=comment)
        # Notify / Send
        for to_addr in to_addrs:
            user = root.get_user(to_addr)
            if not user:
                continue
            to_addr = user.get_property('email')
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
            empty = MSG(u'[empty]').gettext()
        else:
            # New issue
            template = MSG(u'$field: $old_value$new_value')
            empty = u''
        # Modification of title
        last_title = self.get_value('title') or empty
        new_title = record['title']
        if last_title != new_title:
            field = MSG(u'Title').gettext()
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title)
            modifications.append(text)
        # List modifications
        fields = [
            ('module', MSG(u'Module')),
            ('version', MSG(u'Version')),
            ('type', MSG(u'Type')),
            ('priority', MSG(u'Priority')),
            ('state', MSG(u'State'))]
        for name, field in fields:
            field = field.gettext()
            new_value = record[name]
            last_value = self.get_value(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = empty
            csv = self.parent.get_resource(name).handler
            if last_value or last_value == 0:
                rec = csv.get_record(last_value)
                last_title = csv.get_record_value(rec, 'title')
            if new_value or new_value == 0:
                rec = csv.get_record(new_value)
                new_title = csv.get_record_value(rec, 'title')
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
            field = MSG(u'Assigned To').gettext()
            text = template.gettext(field=field, old_value=last_user or empty,
                                    new_value=new_user or empty)
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
            last_values = ', '.join(last_values) or empty
            new_values = ', '.join(new_values) or empty
            text = template.gettext(field=field, old_value=last_values,
                                    new_value=new_values)
            modifications.append(text)

        return u'\n'.join(modifications)


    def get_reported_by(self):
        history = self.get_history()
        return history.get_record(0).username


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


    def get_size(self):
        # FIXME Used by the browse list view (size is indexed)
        return 0


    #######################################################################
    # User Interface
    #######################################################################
    def get_context_menus(self):
        return self.parent.get_context_menus() + [IssueTrackerMenu()]


    edit = Issue_Edit()
    edit_resources = Issue_EditResources()
    history = Issue_History()




###########################################################################
# Register
###########################################################################
register_resource_class(Issue)
