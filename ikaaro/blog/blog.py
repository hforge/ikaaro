# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Matthieu France <matthieu.france@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
from datetime import date

# Import from itools
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.web import STLView

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoform import RTEWidget
from ikaaro.comments import CommentsView
from ikaaro.config import Configuration
from ikaaro.fields import Date_Field
from ikaaro.file_views import File_Edit
from ikaaro.folder import Folder
from ikaaro.messages import MSG_CHANGES_SAVED
from ikaaro.webpage import WebPage


###########################################################################
# Views
###########################################################################
rte = RTEWidget(
    'data', title=MSG(u'Description'),
    toolbar1="newdocument,code,|,bold,italic,underline,strikethrough"
             ",|,undo,redo,|,link,unlink,|,removeformat",
    toolbar2="", toolbar3="",
    width='500px')


class Post_NewInstance(AutoAdd):

    fields = ['title', 'data', 'date']


    def get_field(self, name):
        if name == 'date':
            cls = self._resource_class
            return cls.date(default=date.today())

        return super(Post_NewInstance, self).get_field(name)


    def get_container(self, resource, context, form):
        return resource



class Post_View(STLView):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/blog/Post_view.xml'

    schema = {
        'comment': Unicode(required=True)}


    def get_namespace(self, resource, context):
        return {
            'title': resource.get_value('title'),
            'data': resource.get_html_data(),
            'date': resource.get_value('date'),
            'comments': CommentsView().GET(resource, context)}


    def action(self, resource, context, form):
        resource.add_comment(form['comment'])
        context.message = MSG_CHANGES_SAVED


###########################################################################
# Resource
###########################################################################
class Post(WebPage):

    class_id = 'blog-post'
    class_title = MSG(u'Blog Post')
    class_description = MSG(u'Create and publish Post')
    class_icon16 = 'blog/Blog16.png'
    class_icon48 = 'blog/Blog48.png'
    class_views = ['view', 'edit', 'commit_log']


    # Fields
    date = Date_Field(stored=True, title=MSG(u'Date'))
    title = WebPage.title(required=True)
    data = WebPage.data(widget=rte)

    # Views
    new_instance = Post_NewInstance
    view = Post_View
    edit = File_Edit(fields=['title', 'date', 'data', 'share'])



###########################################################################
# Module
###########################################################################
class Blog(Folder):

    class_id = 'blog'
    class_title = MSG(u'Blog')

    # Configuration
    config_name = '/blog'
    config_group = 'content'

    # API
    def get_document_types(self):
        return [Post]


# Register
Configuration.register_module(Blog)
