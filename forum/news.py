# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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

# Import from ikaaro
from ikaaro.webpage import WebPage
from ikaaro.registry import register_document_type
from ikaaro.views_new import NewInstanceByDate


class News_NewInstance(NewInstanceByDate):

    def get_resource_class(self, context, form):
        return News



class News(WebPage):

    class_id = 'news'
    class_title = MSG(u'News')
    class_description = MSG(u'...')
    class_icon16 = 'icons/16x16/news.png'
    class_icon48 = 'icons/48x48/news.png'


    # Views
    new_instance = News_NewInstance()



###########################################################################
# Register
###########################################################################
register_document_type(News)
