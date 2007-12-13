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

# Import from the Standard Library
from operator import itemgetter

# Import from itools
from itools.handlers import checkid
from itools.i18n import format_datetime
from itools.stl import stl

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.registry import register_object_class
from thread import Thread
from message import Message


class Forum(Folder):

    class_id = 'Forum'
    class_version = '20071119'
    class_title = u'Forum'
    class_description = u'An iKaaro forum'
    class_icon48 = 'forum/Forum48.png'
    class_icon16 = 'forum/Forum16.png'
    class_views = [['view'], ['new_thread_form'], ['edit_metadata_form']]

    thread_class = Thread


    def get_document_types(self):
        return [self.thread_class]


    view__access__ = 'is_allowed_to_view'
    view__label__ = u"View"
    def view(self, context):
        context.styles.append('/ui/forum/forum.css')
        # Namespace
        namespace = {}
        namespace['title'] = self.get_title()
        namespace['description'] = self.get_property('description')
        # Namespace / Threads
        accept_language = context.accept_language
        users = self.get_object('/users')
        namespace['threads'] = []
        for thread in self.search_objects(object_class=Thread):
            message = thread.get_object('0')
            author = users.get_object(message.get_owner())
            posts = thread.search_objects(object_class=Message)
            posts = list(posts)
            namespace['threads'].append({
                'name': thread.name,
                'title': thread.get_title(),
                'author': author.get_title(),
                'date': format_datetime(message.get_mtime(), accept_language),
                'comments': len(posts) - 1,
##                'description': thread.get_property('description'),
            })
        namespace['threads'].sort(key=itemgetter('date'), reverse=True)

        handler = self.get_object('/ui/forum/Forum_view.xml')
        return stl(handler, namespace)


    new_thread_form__access__ = 'is_allowed_to_edit'
    new_thread_form__label__ = u"New Thread"
    def new_thread_form(self, context):
        context.styles.append('/ui/forum/forum.css')

        namespace = {}
        namespace['rte'] =  self.get_rte(context, 'data', None)

        handler = self.get_object('/ui/forum/Forum_new_thread.xml')
        return stl(handler, namespace)


    new_thread__access__ = 'is_allowed_to_edit'
    def new_thread(self, context):
        title = context.get_form_value('dc:title').strip()
        if not title:
            return context.come_back(u"No title given.")

        name = checkid(title)
        if name is None:
            return context.come_back(u"Invalid title.")

        if self.has_object(name):
            return context.come_back(u"This thread already exists.")

        language = self.get_content_language()
        cls = self.thread_class
        data = context.get_form_value('data')
        thread = cls.make_object(cls, self, name, data, language)
        thread.set_property('title', title, language=language)

        return context.come_back(u"Thread Created.", goto=name)


    # Used by "get_rte" above
    def get_epoz_data(self):
        # Default document for new thread form
        return None


    #######################################################################
    # Update
    #######################################################################
    def update_20071119(self):
        Folder.update_20071119(self)



###########################################################################
# Register
###########################################################################
register_object_class(Forum)
