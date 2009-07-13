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

# Import from itools
from itools.csv import Property
from itools.datatypes import Integer, String, Unicode, Tokens
from itools.gettext import MSG
from itools.handlers import checkid
from itools.vfs import FileName
from itools.uri import get_uri_path
from itools.web import get_context

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.registry import register_resource_class, get_resource_class
from ikaaro.registry import register_field
from ikaaro.utils import generate_name
from issue_views import Issue_Edit, Issue_EditResources, Issue_History
from issue_views import IssueTrackerMenu


class Issue(Folder):

    class_id = 'issue'
    class_version = '20071216'
    class_title = MSG(u'Issue')
    class_description = MSG(u'Issue')
    class_views = ['edit', 'edit_resources', 'browse_content', 'history']


    @classmethod
    def get_metadata_schema(cls):
        schema = Folder.get_metadata_schema()
        schema['product'] = Integer
        schema['module'] = Integer
        schema['version'] = Integer
        schema['type'] = Integer
        schema['state'] = Integer
        schema['priority'] = Integer
        schema['assigned_to'] = String
        schema['cc_list'] = Tokens
        # parameters: date, author, file
        schema['comment'] = Unicode(multiple=True)
        return schema


    def _get_catalog_values(self):
        document = Folder._get_catalog_values(self)
        document['id'] = int(self.name)
        names = 'product', 'module', 'version', 'type', 'priority', 'state'
        for name in names:
            document[name] = self.get_property(name)
        document['assigned_to'] = self.get_property('assigned_to') or 'nobody'
        return document


    def get_document_types(self):
        return [File]


    def get_links(self):
        base = self.get_abspath()

        comments = self.metadata.get_property('comment')
        if comments is None:
            return []

        links = []
        for comment in comments:
            filename = comment.parameters.get('file')
            if filename:
                links.append(str(base.resolve2(filename)))
        return links


    def update_links(self, old_path, new_path):
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
        return u'#%s %s' % (self.name, self.get_property('title'))


    def get_calendar(self):
        return self.parent.get_resource('calendar')


    def get_history(self):
        raise NotImplementedError, 'this method is to be removed'


    def _add_record(self, context, form, new=False):
        # Title
        title = form['title'].strip()
        language = self.get_content_language(context)
        self.set_property('title', title, language=language)
        # Version, Priority, etc.
        schema = self.get_metadata_schema()
        for name in ['product', 'module', 'version', 'type', 'state',
                     'priority', 'assigned_to']:
            value = form[name]
            self.set_property(name, value)
        # CCs
        if new:
            cc_add = form['cc_add']
            if cc_add:
                self.set_property('cc_list', tuple(cc_add))
        else:
            cc_list = self.get_property('cc_list')
            cc_list = set(cc_list)
            cc_remove = form['cc_remove']
            if cc_remove:
                cc_remove = form['cc_list']
                cc_list = cc_list.difference(cc_remove)
            cc_add = form['cc_add']
            cc_list = cc_list.union(cc_add)
            self.set_property('cc_list', tuple(cc_list))

        # Files XXX
        file = form['file']
        if file is not None:
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
            file = name

        # Comment
        now = datetime.now()
        user = context.user
        author = user.name if user else None
        comment = form['comment']
        comment = Property(comment, date=now, author=author, file=file)
        self.set_property('comment', comment)

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
        assigned_to = self.get_property('assigned_to')
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
        body = '#%s %s %s\n\n' % (self.name, self.get_property('title'), uri)
        message = MSG(u'The user {title} did some changes.')
        body +=  message.gettext(title=user_title)
        body += '\n\n'
        if file:
            filename = unicode(filename, 'utf-8')
            message = MSG(u'New Attachment: {filename}')
            message = message.gettext(filename=filename)
            body += message + '\n'
        comment = context.get_form_value('comment', type=Unicode)
        modifications = self.get_diff_with(record, context, new=new)
        if modifications:
            body += modifications
            body += '\n\n'
        if comment:
            title = MSG(u'Comment').gettext()
            separator = len(title) * u'-'
            template = u'{title}\n{separator}\n\n{comment}\n'
            body += template.format(title=title, separator=separator,
                                    comment=comment)
        # Notify / Send
        root = context.root
        for to_addr in to_addrs:
            user = root.get_user(to_addr)
            if not user:
                continue
            to_addr = user.get_property('email')
            root.send_email(to_addr, subject, text=body)


    def get_diff_with(self, record, context, new=False):
        """Return a text with the diff between the last and new issue state.
        """
        root = context.root
        modifications = []
        if new:
            # New issue
            template = MSG(u'{field}: {old_value}{new_value}')
            empty = u''
        else:
            # Edit issue
            template = MSG(u'{field}: {old_value} to {new_value}')
            empty = MSG(u'[empty]').gettext()
        # Modification of title
        last_title = self.get_property('title') or empty
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
            last_value = self.get_property(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = empty
            csv = self.parent.get_resource(name).handler
            if last_value or last_value == 0:
                rec = csv.get_record(last_value)
                if rec is None:
                    last_title = 'undefined'
                else:
                    last_title = csv.get_record_value(rec, 'title')
            if new_value or new_value == 0:
                rec = csv.get_record(new_value)
                new_title = csv.get_record_value(rec, 'title')
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title)
            modifications.append(text)

        # Modifications of assigned_to
        last_user = self.get_property('assigned_to') or ''
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
        last_cc = self.get_property('cc_list')
        last_cc = list(last_cc) if last_cc else []
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
        comments = self.metadata.get_property('comment')
        return comments[0].parameters['author']


    def to_text(self):
        comments = self.get_property('comment')
        return u'\n'.join(comments)


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
# The class
register_resource_class(Issue)


# The fields
for name in ['id', 'product', 'module', 'version', 'type', 'state',
             'priority']:
    register_field(name, Integer(is_stored=True, is_indexed=True))
register_field('assigned_to', String(is_stored=True, is_indexed=True))

