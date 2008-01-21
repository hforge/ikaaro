# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from itools
from itools.datatypes import FileName
from itools.i18n import format_datetime
from itools.stl import stl

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.messages import MSG_DELETE_SELECTION, MSG_CHANGES_SAVED
from ikaaro.registry import register_object_class
from message import Message, build_message


class Thread(Folder):

    class_id = 'ForumThread'
    class_version = '20071215'
    class_title = u"Thread"
    class_description = u"A thread to discuss"
    class_views = [['view'], ['edit_metadata_form']]

    message_class = Message

    addlink_form__access__ = False
    addimage_form__access__ = False
    epoz_table_form__access__ = False


    @staticmethod
    def _make_object(cls, folder, name, data=u'', language='en'):
        Folder._make_object(cls, folder, name)
        # First post
        cls = cls.message_class
        folder.set_handler('%s/0.metadata' % name, cls.build_metadata())
        message = build_message(data)
        folder.set_handler('%s/0.xhtml.%s' % (name, language), message)


    def get_context_menu_base(self):
        # Show actions of the forum
        return self.parent


    def to_text(self):
        # Index the thread by the content of all its posts
        text = [ x.to_text()
                 for x in self.search_objects(object_class=Message) ]

        return u'\n'.join(text)


    def get_document_types(self):
        return [self.message_class]


    def get_posts(self):
        posts = [ (int(FileName.decode(x.name)[0]), x)
                  for x in self.search_objects(object_class=Message) ]
        posts.sort()
        return [ x[1] for x in posts ]


    def get_last_post_id(self):
        posts = self.search_objects(object_class=Message)
        ids = [ int(x.name) for x in posts ]
        return max(ids)


    view__access__ = 'is_allowed_to_view'
    view__label__ = u"View"
    view__icon__ = '/ui/images/view16.png'
    def view(self, context):
        context.styles.append('/ui/forum/forum.css')

        user = context.user
        users = self.get_object('/users')
        ac = self.get_access_control()
        accept_language = context.accept_language
        # The namespace
        namespace = {}
        namespace['title'] = self.get_title()
        namespace['description'] = self.get_property('description')
        namespace['editable'] = ac.is_admin(user, self)
        # Actions
        actions = []
        message = self.gettext(MSG_DELETE_SELECTION)
        remove_message = 'return confirmation("%s");' % message.encode('utf_8')
        namespace['remove_message'] = remove_message

        namespace['messages'] = []
        for message in self.get_posts():
            author_id = message.get_owner()
            namespace['messages'].append({
                'name': message.name,
                'author': users.get_object(author_id).get_title(),
                'mtime': format_datetime(message.get_mtime(), accept_language),
                'body': message.handler.events,
            })
        namespace['is_allowed_to_add'] = ac.is_allowed_to_add(user, self)
        if namespace['is_allowed_to_add']:
            namespace['rte'] = self.get_rte(context, 'data', None)

        handler = self.get_object('/ui/forum/Thread_view.xml')
        return stl(handler, namespace)


    new_reply__access__ = 'is_allowed_to_add'
    epoz_iframe__access__ = 'is_allowed_to_add'
    def new_reply(self, context):
        # check input
        data = context.get_form_value('data').strip()
        if not data:
            message = (
              u'Some required fields are missing, or some values are not valid.'
              u' Please correct them and continue.')
            return context.come_back(message)

        # Find out the name for the new post
        id = self.get_last_post_id()
        name = str(id + 1)

        # Post
        language = self.get_content_language()
        cls = self.message_class
        cls.make_object(cls, self, name, data, language)

        # Change
        context.server.change_object(self)

        return context.come_back(u"Reply Posted.", goto='#new_reply')


    remove_reply__access__ = 'is_admin'
    def remove_reply(self, context):
        come_back = Folder.remove(self, context)

        # Change
        context.server.change_object(self)

        return come_back


    # Used by "get_rte" above
    def get_epoz_data(self):
        # Default document for new message form
        return None


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self):
        Folder.update_20071215(self)



###########################################################################
# Register
###########################################################################
register_object_class(Thread)
