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

# Import from itools
from itools.core import merge_dicts
from itools.csv import Property
from itools.datatypes import Integer, String, Unicode, Tokens
from itools.gettext import MSG
from itools.handlers import checkid
from itools.fs import FileName
from itools.uri import Path
from itools.web import get_context

# Import from ikaaro
from ikaaro.comments import CommentsAware
from ikaaro.folder import Folder
from ikaaro.metadata import Metadata
from ikaaro.obsolete.metadata import OldMetadata
from ikaaro.registry import get_resource_class
from ikaaro.utils import generate_name
from issue_views import Issue_DownloadAttachments, Issue_Edit
from issue_views import Issue_History, IssueTrackerMenu


class Issue(CommentsAware, Folder):

    class_id = 'issue'
    class_version = '20100507'
    class_title = MSG(u'Issue')
    class_description = MSG(u'Issue')
    class_views = ['edit', 'edit_resources', 'browse_content', 'history']


    class_schema = merge_dicts(
        Folder.class_schema,
        CommentsAware.class_schema,
        # Metadata
        product=Integer(source='metadata', indexed=True, stored=True),
        module=Integer(source='metadata', indexed=True, stored=True),
        version=Integer(source='metadata', indexed=True, stored=True),
        type=Integer(source='metadata', indexed=True, stored=True),
        state=Integer(source='metadata', indexed=True, stored=True),
        priority=Integer(source='metadata', indexed=True, stored=True),
        assigned_to=String(source='metadata', indexed=True, stored=True),
        cc_list=Tokens(source='metadata'),
        # Other
        id=Integer(indexed=True, stored=True),
        attachment=String(source='metadata', multiple=True))


    def get_catalog_values(self):
        document = Folder.get_catalog_values(self)
        document['id'] = int(self.name)
        # Override default (FIXME should set default to 'nobody' instead?)
        document['assigned_to'] = self.get_property('assigned_to') or 'nobody'
        return document


    def get_document_types(self):
        return []


    def get_links(self):
        attachments = self.metadata.get_property('attachment')
        if not attachments:
            return set()

        base = self.get_canonical_path()
        return set([ str(base.resolve2(x.value)) for x in attachments ])


    def update_links(self, source, target):
        base = self.get_canonical_path()
        resources_new2old = get_context().database.resources_new2old
        base = str(base)
        old_base = resources_new2old.get(base, base)
        old_base = Path(old_base)
        new_base = Path(base)

        attachments = self.metadata.get_property('attachment')
        new_attachments = []
        for attachment in attachments:
            path = old_base.resolve2(str(attachment.value))
            if path == source:
                value = str(new_base.get_pathto(target))
                new_attachments.append(value)
            else:
                new_attachments.append(attachment)

        self.set_property('attachment', new_attachments)
        get_context().database.change_resource(self)


    #######################################################################
    # API
    #######################################################################
    def get_title(self, language=None):
        return u'#%s %s' % (self.name, self.get_property('title'))


    def get_history(self):
        context = get_context()
        database = context.database
        filename = '%s.metadata' % self.get_abspath()
        filename = filename[1:]

        get_blob = database.get_blob_by_revision_and_path

        for hash in database.get_commit_hashs(filename):
            try:
                yield get_blob(hash, filename, Metadata)
            except SyntaxError:
                yield get_blob(hash, filename, OldMetadata)


    def add_comment(self, context, form, new=False):
        # Keep a copy of the current metadata
        old_metadata = self.metadata.clone()
        # Title
        title = form['title'].strip()
        language = self.get_edit_languages(context)[0]
        self.set_property('title', title, language=language)
        # Version, Priority, etc.
        for name in ['product', 'module', 'version', 'type', 'state',
                     'priority', 'assigned_to']:
            value = form[name]
            self.set_property(name, value)
        # CCs
        cc_list = form['cc_list']
        self.set_property('cc_list', tuple(cc_list))

        # Attachment
        attachment = form['attachment']
        if attachment is not None:
            # Upload
            filename, mimetype, body = form['attachment']
            # Find a non used name
            name = checkid(filename)
            name, extension, language = FileName.decode(name)
            name = generate_name(name, self.get_names())
            # Add attachment
            cls = get_resource_class(mimetype)
            self.make_resource(name, cls, body=body, filename=filename,
                               extension=extension, format=mimetype)
            # Link
            attachment = name
            self.set_property('attachment', attachment)

        # Comment
        date = context.timestamp
        user = context.user
        author = user.name if user else None
        comment = form['comment']
        comment = Property(comment, date=date, author=author)
        self.set_property('comment', comment)

        # Send a Notification Email
        # Notify / From
        if user is None:
            user_title = MSG(u'ANONYMOUS')
        else:
            user_title = user.get_title()
        # Notify / To
        to_addrs = set(cc_list)
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
        # Notify / Build the message for each language
        site_root = self.get_site_root()
        website_languages = site_root.get_property('website_languages')
        default_language = site_root.get_default_language()
        messages_dict = {}
        for language in website_languages:
            message = MSG(u'DO NOT REPLY TO THIS EMAIL. To comment on this '
                    u'issue, please visit:\n{issue_uri}')
            body = message.gettext(issue_uri=uri, language=language)
            body += '\n\n'
            body += '#%s %s\n\n' % (self.name, self.get_property('title'))
            message = MSG(u'The user {title} did some changes.')
            body +=  message.gettext(title=user_title, language=language)
            body += '\n\n'
            if attachment is not None:
                u_filename = unicode(filename, 'utf-8')
                message = MSG(u'New Attachment: {filename}')
                message = message.gettext(filename=u_filename,
                                          language=language)
                body += message + '\n'
            comment = context.get_form_value('comment', type=Unicode)
            modifications = self.get_diff_with(old_metadata, context, new=new,
                                              language=language)
            if modifications:
                body += modifications
                body += '\n\n'
            if comment:
                title = MSG(u'Comment').gettext(language=language)
                separator = len(title) * u'-'
                template = u'{title}\n{separator}\n\n{comment}\n'
                body += template.format(title=title, separator=separator,
                                        comment=comment)
            # OK
            messages_dict[language] = subject, body
        # Notify / Send
        root = context.root
        for to_addr in to_addrs:
            user = root.get_user(to_addr)
            if not user:
                continue
            to_addr = user.get_property('email')
            language = user.get_property('user_language')
            if language not in website_languages:
                language = default_language
            subject, body = messages_dict[language]
            root.send_email(to_addr, subject, text=body)


    def get_diff_with(self, old_metadata, context, new=False, language=None):
        """Return a text with the diff between the given Metadata and new
        issue state.
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
            empty = MSG(u'[empty]').gettext(language=language)
        # Modification of title
        last_prop = old_metadata.get_property('title')
        last_title = last_prop.value if last_prop else empty
        new_title = self.get_property('title') or empty
        if last_title != new_title:
            field = MSG(u'Title').gettext(language=language)
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title, language=language)
            modifications.append(text)
        # List modifications
        fields = [
            ('product', MSG(u'Product')),
            ('module', MSG(u'Module')),
            ('version', MSG(u'Version')),
            ('type', MSG(u'Type')),
            ('priority', MSG(u'Priority')),
            ('state', MSG(u'State'))]
        for name, field in fields:
            field = field.gettext(language=language)
            last_prop = old_metadata.get_property(name)
            last_value = last_prop.value if last_prop else None
            new_value = self.get_property(name)
            # Detect if modifications
            if last_value == new_value:
                continue
            new_title = last_title = empty
            csv = self.parent.get_resource(name).handler
            if last_value or last_value == 0:
                rec = csv.get_record(last_value)
                if rec is None:
                    last_title = MSG(u'undefined').gettext(language=language)
                else:
                    last_title = csv.get_record_value(rec, 'title', language)
                    if not last_title:
                        last_title = csv.get_record_value(rec, 'title')
            if new_value or new_value == 0:
                rec = csv.get_record(new_value)
                new_title = csv.get_record_value(rec, 'title', language)
                if not new_title:
                    new_title = csv.get_record_value(rec, 'title')
            text = template.gettext(field=field, old_value=last_title,
                                    new_value=new_title, language=language)
            modifications.append(text)

        # Modifications of assigned_to
        new_user = self.get_property('assigned_to') or ''
        last_prop = old_metadata.get_property('assigned_to')
        last_user = last_prop.value if last_prop else None
        if last_user != new_user:
            if last_user:
                last_user = root.get_user(last_user).get_property('email')
            if new_user:
                new_user = root.get_user(new_user).get_property('email')
            field = MSG(u'Assigned To').gettext(language=language)
            text = template.gettext(field=field, old_value=last_user or empty,
                                    new_value=new_user or empty,
                                    language=language)
            modifications.append(text)

        # Modifications of cc_list
        last_prop = old_metadata.get_property('cc_list')
        last_cc = list(last_prop.value) if last_prop else ()
        new_cc = self.get_property('cc_list')
        new_cc = list(new_cc) if new_cc else []
        if last_cc != new_cc:
            last_values = []
            for cc in last_cc:
                value = root.get_user(cc).get_property('email')
                last_values.append(value)
            new_values = []
            for cc in new_cc:
                value = root.get_user(cc).get_property('email')
                new_values.append(value)
            field = MSG(u'CC').gettext(language=language)
            last_values = ', '.join(last_values) or empty
            new_values = ', '.join(new_values) or empty
            text = template.gettext(field=field, old_value=last_values,
                                    new_value=new_values, language=language)
            modifications.append(text)

        return u'\n'.join(modifications)


    def get_reported_by(self):
        comments = self.metadata.get_property('comment')
        return comments[0].get_parameter('author')


    def to_text(self):
        comments = self.get_property('comment')
        return u'\n'.join(comments)


    #######################################################################
    # User Interface
    #######################################################################
    def get_context_menus(self):
        return self.parent.get_context_menus() + [IssueTrackerMenu()]


    download_attachments = Issue_DownloadAttachments()
    edit = Issue_Edit()
    history = Issue_History()


    #######################################################################
    # Update
    #######################################################################
    def update_20100507(self):
        from itools.core import fixed_offset
        from obsolete import History

        metadata = self.metadata
        history = self.handler.get_handler('.history', History)

        record = history.records[-1]
        # Title
        lang = self.get_site_root().get_default_language()
        title = history.get_record_value(record, 'title')
        title = Property(title, lang=lang)
        metadata.set_property('title', title)
        # Product, module, etc.
        names = 'product', 'module', 'version', 'type', 'state', 'priority'
        for name in names:
            value = history.get_record_value(record, name)
            if value is not None:
                metadata.set_property(name, value)
        # Assigned
        value = history.get_record_value(record, 'assigned_to')
        if value:
            metadata.set_property('assigned_to', value)

        # Comments / Files
        utc = fixed_offset(0)
        attachments = []
        for record in history.records:
            if record is None:
                # deleted record
                continue
            comment = history.get_record_value(record, 'comment')
            date = history.get_record_value(record, 'datetime')
            date = date.replace(tzinfo=utc)
            author = history.get_record_value(record, 'username')
            comment = Property(comment, date=date, author=author)
            metadata.set_property('comment', comment)
            file = history.get_record_value(record, 'file')
            if file:
                attachments.append(file)
        if attachments:
            metadata.set_property('attachment', attachments)

        # CC
        reporter = history.records[0].username
        value = history.get_record_value(record, 'cc_list')
        if reporter not in value:
            value = value + (reporter,)
        metadata.set_property('cc_list', value)

        # Remove .history
        self.handler.del_handler('.history')
