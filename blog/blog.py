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
from itools.core import freeze, merge_dicts
from itools.csv import Property
from itools.datatypes import Date, Unicode
from itools.gettext import MSG
from itools.web import STLForm

# Import from ikaaro
from ikaaro.autoform import DateWidget, HTMLBody, RTEWidget
from ikaaro.autoform import timestamp_widget, title_widget
from ikaaro.comments import comment_datatype, CommentsView
from ikaaro.folder import Folder
from ikaaro.messages import MSG_NEW_RESOURCE, MSG_CHANGES_SAVED
from ikaaro.views_new import NewInstance
from ikaaro.webpage import HTMLEditView, WebPage
from ikaaro.workflow import state_widget


###########################################################################
# Views
###########################################################################
rte = RTEWidget(
    'data', title=MSG(u'Description'),
    toolbar1="newdocument,code,|,bold,italic,underline,strikethrough"
             ",|,undo,redo,|,link,unlink,|,removeformat",
    toolbar2="", toolbar3="",
    width='500px')


class Post_NewInstance(NewInstance):

    widgets = NewInstance.widgets + [
        DateWidget('date', title=MSG(u'Date')),
        rte]


    def get_schema(self, resource, context):
        return merge_dicts(
            NewInstance.schema,
            title=Unicode(mandatory=True),
            data=HTMLBody,
            date=Date(default=date.today()))


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']
        html = form['data']
        release_date = form['date']

        # Make Object
        language = resource.get_edit_languages(context)[0]
        post = resource.make_resource(name, Post, language=language)
        handler = post.get_handler(language=language)
        handler.set_body(html)
        post.metadata.set_property('title', Property(title, lang=language))
        post.metadata.set_property('date', release_date)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class Post_View(STLForm):

    access = 'is_allowed_to_view'
    title = MSG(u'View')
    template = '/ui/blog/Post_view.xml'

    schema = {
        'comment': Unicode(required=True)}


    def get_namespace(self, resource, context):
        return {
            'title': resource.get_property('title'),
            'data': resource.get_html_data(),
            'date': resource.get_property('date'),
            'comments': CommentsView().GET(resource, context)}


    def action(self, resource, context, form):
        date = context.timestamp
        author = context.user.name if context.user else None
        comment = Property(form['comment'], date=date, author=author)
        resource.set_property('comment', comment)
        # Change
        context.database.change_resource(resource)
        context.message = MSG_CHANGES_SAVED



class Post_Edit(HTMLEditView):

    def _get_schema(self, resource, context):
        return merge_dicts(HTMLEditView._get_schema(self, resource, context),
                           date=Date)

    widgets = freeze([
        timestamp_widget,
        title_widget,
        DateWidget('date', title=MSG(u'Date')),
        state_widget,
        rte])


    def set_value(self, resource, context, name, form):
        if name == 'date':
            resource.set_property('date', form['date'])
            return False
        return HTMLEditView.set_value(self, resource, context, name, form)


###########################################################################
# Resource
###########################################################################
class Post(WebPage):

    class_id = 'blog-post'
    class_title = MSG(u'Post')
    class_description = MSG(u'Create and publish Post')
    class_views = ['view', 'edit', 'commit_log']


    class_schema = merge_dicts(
        WebPage.class_schema,
        date=Date(source='metadata', stored=True),
        comment=comment_datatype)


    # Views
    new_instance = Post_NewInstance()
    view = Post_View()
    edit = Post_Edit()



class Blog(Folder):

    class_id = 'blog'
    class_title = MSG(u'Blog')
    class_icon16 = 'blog/Blog16.png'
    class_icon48 = 'blog/Blog48.png'

    def get_document_types(self):
        return [Post]
