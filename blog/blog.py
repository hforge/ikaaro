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
from datetime import date, datetime

# Import from itools
from itools.core import freeze, merge_dicts
from itools.csv import Property
from itools.datatypes import Date, DateTime, String, Unicode
from itools.handlers import checkid
from itools.gettext import MSG
from itools.web import STLForm
from itools.xml import XMLError, XMLParser

# Import from ikaaro
from ikaaro.autoform import DateWidget, RTEWidget
from ikaaro.autoform import timestamp_widget, title_widget
from ikaaro.comments import CommentsView
from ikaaro.folder import Folder
from ikaaro.messages import *
from ikaaro.resource_views import DBResource_Edit
from ikaaro.views_new import NewInstance
from ikaaro.webpage import WebPage


###########################################################################
# Views
###########################################################################
rte = RTEWidget(
    'html', title=MSG(u'Description'),
    toolbar1="newdocument,code,|,bold,italic,underline,strikethrough"
             ",|,undo,redo,|,link,unlink,|,removeformat",
    toolbar2="", toolbar3="",
    width='500px')


class Post_NewInstance(NewInstance):

    widgets = NewInstance.widgets + [
        DateWidget('date', title=MSG(u'Date')),
        rte]


    def get_schema(self, resource, context):
        return {
            'name': String,
            'title': Unicode(mandatory=True),
            'html': String,
            'date': Date(default=date.today())}


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']
        html = form['html']
        release_date = form['date']

        name = checkid(name)
        if name is None:
            context.message = MSG_BAD_NAME
            return

        # Check the name is free
        if resource.get_resource(name, soft=True):
            context.message = MSG_NAME_CLASH
            return

        # Make Object
        language = resource.get_content_language(context)
        post = resource.make_resource(name, Post, body=html, language=language)
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
        language = resource.get_content_language(context)
        return {
            'title': resource.get_property('title', language=language),
            'html': resource.handler.events,
            'date': resource.get_property('date'),
            'comments': CommentsView().GET(resource, context)}


    def action(self, resource, context, form):
        date = context.timestamp
        author = context.user.name if context.user else None
        comment = Property(form['comment'], date=date, author=author)
        resource.set_property('comment', comment)
        # Change
        context.server.change_resource(resource)
        context.message = MSG_CHANGES_SAVED



class Post_Edit(DBResource_Edit):

    schema = {
        'title': Unicode(mandatory=True),
        'date': Date,
        'html': String,
        'timestamp': DateTime}

    widgets = freeze([
        timestamp_widget,
        title_widget,
        DateWidget('date', title=MSG(u'Date')),
        rte])


    def get_value(self, resource, context, name, datatype):
        if name == 'html':
            return resource.handler.events
        return DBResource_Edit.get_value(self, resource, context, name,
                                         datatype)


    def action(self, resource, context, form):
        # Check edit conflict
        self.check_edit_conflict(resource, context, form)
        if context.edit_conflict:
            return

        # Check the html is good
        html = form['html']
        try:
            html = list(XMLParser(html))
        except XMLError:
            context.message = MSG(u'Invalid HTML code.')
            return

        # Save changes
        language = resource.get_content_language(context)
        resource.set_property('title', form['title'], language=language)
        resource.set_property('date', form['date'])
        resource.handler.set_events(html)
        # Ok
        context.message = MSG_CHANGES_SAVED


###########################################################################
# Resource
###########################################################################
class Post(WebPage):

    class_id = 'blog-post'
    class_title = MSG(u'Post')
    class_description = MSG(u'Create and publish Post')
    class_views = ['view', 'edit', 'edit_state', 'history']


    class_schema = merge_dicts(
        WebPage.class_schema,
        date=Date(source='metadata', stored=True),
        comment=Unicode(source='metadata', multiple=True))


    def _get_catalog_values(self):
        indexes = WebPage._get_catalog_values(self)
        indexes['date'] = self.get_property('date')
        return indexes


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
