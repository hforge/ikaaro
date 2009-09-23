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
from itools.fs import FileName
from itools.gettext import MSG
from itools.handlers import checkid
from itools.http import get_context
from itools.uri import Path

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.registry import get_resource_class, register_field
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


    def get_document_types(self):
        return [File]


    #######################################################################
    # Indexing
    #######################################################################
    @property
    def id(self):
        return int(self.name)


    @property
    def product(self):
        return self.get_property('product')


    @property
    def module(self):
        return self.get_property('module')


    @property
    def version(self):
        return self.get_property('version')


    @property
    def type(self):
        return self.get_property('type')


    @property
    def priority(self):
        return self.get_property('priority')


    @property
    def state(self):
        return self.get_property('state')


    @property
    def assigned_to(self):
        return self.get_property('assigned_to') or 'nobody'


    #######################################################################
    # API
    #######################################################################
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


    def update_links(self, source, target):
        base = self.get_abspath()
        resources_new2old = get_context().database.resources_new2old
        base = str(base)
        old_base = resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)

        history = self.get_history()
        for record in history.get_records():
            filename = history.get_record_value(record, 'file')
            if not filename:
                continue
            path = old_base.resolve2(filename)
            if path == source:
                value = str(new_base.get_pathto(target))
                history.update_record(record.id, **{'file': value})

        get_context().database.change_resource(self)


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
            self.make_resource(name, cls, body=body, filename=filename,
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
        if isinstance(context.resource, self.__class__):
            uri = context.uri.resolve(';edit')
        else:
            uri = context.uri.resolve('%s/;edit' % self.name)

        message = MSG(u'DO NOT REPLY TO THIS EMAIL. To comment on this '
                u'issue, please visit:\n{issue_uri}')
        body = message.gettext(issue_uri=uri)
        body += '\n\n'
        body += '#%s %s\n\n' % (self.name, self.get_property('title'))
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
for name in ['id', 'product', 'module', 'version', 'type', 'state',
             'priority']:
    register_field(name, Integer(is_stored=True, is_indexed=True))
register_field('assigned_to', String(is_stored=True, is_indexed=True))

