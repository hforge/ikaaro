# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.gettext import MSG
from itools.web import BaseView

# Import from ikaaro
from autoadd import AutoAdd
from database import Database
from fields import HTMLFile_Field
from file import File



class WebPage_View(BaseView):
    access = 'is_allowed_to_view'
    title = MSG(u'View')
    icon = 'view.png'


    def GET(self, resource, context):
        return resource.get_html_data()



###########################################################################
# Model
###########################################################################
class WebPage(File):

    class_id = 'webpage'
    class_title = MSG(u'Web Page')
    class_description = MSG(u'Create and publish a Web Page.')
    class_icon16 = 'icons/16x16/html.png'
    class_icon48 = 'icons/48x48/html.png'


    data = HTMLFile_Field(title=MSG(u'Body'))


    #######################################################################
    # API
    #######################################################################
    def get_content_type(self):
        return 'application/xhtml+xml; charset=UTF-8'


    # XXX Obsolete: remove and call 'get_html_field_body_stream' instead
    def get_html_data(self, language=None):
        return self.get_html_field_body_stream('data', language)


    def to_text(self, languages=None):
        if languages is None:
            languages = self.get_root().get_value('website_languages')
        result = {}
        for language in languages:
            handler = self.get_value('data', language=language)
            if handler:
                result[language] = handler.to_text()
        return result


    #######################################################################
    # Views
    #######################################################################
    new_instance = AutoAdd(fields=['title', 'location', 'data'])
    view = WebPage_View



###########################################################################
# Register
###########################################################################
Database.register_resource_class(WebPage, 'application/xhtml+xml')
