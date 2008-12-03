# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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
from itools.datatypes import Unicode, String
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import format_datetime
from itools.web import STLForm, INFO

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro import messages
from ikaaro.forms import title_widget, rte_widget, AutoForm
from ikaaro.registry import register_resource_class
from thread import Thread
from message import Message



class Forum_View(STLForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/forum/Forum_view.xml'

    def get_namespace(self, resource, context):
        context.styles.append('/ui/forum/forum.css')
        # Threads
        accept_language = context.accept_language
        users = resource.get_resource('/users')
        threads = []
        for thread in resource.search_resources(cls=Thread):
            message = thread.get_resource('0')
            author = users.get_resource(message.get_owner())
            posts = thread.search_resources(cls=Message)
            posts = list(posts)
            threads.append({
                'name': thread.name,
                'title': thread.get_title(),
                'author': author.get_title(),
                'date': format_datetime(message.get_mtime(), accept_language),
                'comments': len(posts) - 1,
                'description': thread.get_property('description')})
        threads.sort(key=itemgetter('date'), reverse=True)
        # Ok
        return {
            'title': resource.get_title(),
            'description': resource.get_property('description'),
            'threads': threads}



class AddThreadForm(AutoForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Add a thread')
    icon = 'new.png'

    schema = {
        'title': Unicode(mandatory=True),
        'data': String(mandatory=True)}

    widgets = [title_widget, rte_widget]


    def action(self, resource, context, form):
        # Add
        title = form['title']
        name = checkid(title)
        if name is None:
            context.message = MSG(u"Invalid title.")
            return

        data = form['data'].strip()
        if not data:
            context.message = MSG(u"Thread can't be None.")
            return

        # Check the name is free
        if resource.has_resource(name):
            context.message = messages.MSG_NAME_CLASH
            return

        language = resource.get_content_language(context)
        thread = Thread.make_resource(Thread, resource, name, data, language)
        thread.set_property('title', title, language=language)

        # Ok
        message = INFO(u'Thread Created.')
        goto = './%s/' % name
        return context.come_back(message, goto=goto)



class Forum(Folder):

    class_id = 'Forum'
    class_version = '20071215'
    class_title = MSG(u'Forum')
    class_description = MSG(u'An iKaaro forum')
    class_icon16 = 'forum/Forum16.png'
    class_icon48 = 'forum/Forum48.png'
    class_views = ['view', 'add_thread', 'edit']


    # Views
    view = Forum_View()
    add_thread = AddThreadForm()




###########################################################################
# Register
###########################################################################
register_resource_class(Forum)
