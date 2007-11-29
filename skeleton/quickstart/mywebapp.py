# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
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
from datetime import date

# Import from itools
from itools import get_abspath

# Import from ikaaro
from ikaaro.future.order import OrderAware
from ikaaro.future.dressable import Dressable
from ikaaro.future.menu import get_menu_namespace, Link
from ikaaro.html import WebPage
from ikaaro.registry import register_object_class, register_website
from ikaaro.skins import Skin as BaseSkin, register_skin
from ikaaro.website import WebSite
from ikaaro.binary import Image
from ikaaro.workflow import WorkflowAware

# Import from itws
from utils import is_back_office



###########################################################################
# Skin
###########################################################################
class Skin(BaseSkin):

    class_id = 'mywebapp-skin'


    def build_namespace(self, context):
        namespace = BaseSkin.build_namespace(self, context)
        namespace['tabs'] = get_menu_namespace(context, depth=2,
                                               show_first_child=False,
                                               link_like=Link)
        namespace['today'] = date.today().strftime('%A, %B %d, %Y')
        return namespace



###########################################################################
# Web Site
###########################################################################
class Home(Dressable):
    class_id = 'mywebapp-home'
    class_title = u'Home'
    __fixed_handlers__ = ['left', 'right']
    schema = {'left': ('left', WebPage),
              'right': ('right', WebPage)}
    template = '/ui/webapp/Home_view.xml'

    view__access__ = True


class Section(OrderAware, Dressable, WorkflowAware):
    class_id = 'mywebapp-section'
    class_title = 'Section'
    orderable_classes = (Dressable, Link)
    class_views = (Dressable.class_views +
                   [['state_form']] +
                   [['order_folders_form']])
    __fixed_handlers__ = ['index', 'image']
    schema = {'content': ('index', WebPage),
              'image': ('image', Image)}
    template = '/ui/webapp/Section_view.xml'

    order_folders_form__label__ = u'Menu'
    state_form__access__ = 'is_allowed_to_edit'


    def get_document_types(self):
        return Dressable.get_document_types(self) + [Link, Section]



class MyWebApp(OrderAware, WebSite):

    class_id = 'mywebapp'
    class_title = u'My web application'
    class_views = WebSite.class_views + [['order_folders_form']]
    class_skin = 'ui/webapp'

    orderable_classes = (Home, Section, Link)
    __fixed_handlers__ = WebSite.__fixed_handlers__ + ['home']

    browse_content__access__ = 'is_authenticated'
    last_changes__access__ = 'is_authenticated'
    order_folders_form__label__ = u'Menu'


    @staticmethod
    def _make_object(cls, folder, name):
        WebSite._make_object(cls, folder, name)
        base_name = '%s/home' % name
        metadata = Home.build_metadata()
        folder.set_handler('%s.metadata' % base_name, metadata)
        Dressable._populate(Home, folder, base_name)


    def is_allowed_to_view(self, user, object):
        if is_back_office() is True and user is None:
            return False
        elif isinstance(object, Image) and object.name == 'image':
            return True

        return WebSite.is_allowed_to_view(self, user, object)


    def get_document_types(self):
        return WebSite.get_document_types(self) + [Section, Link, Dressable]


    #######################################################################
    # User Interface
    #######################################################################
    def GET(self, context):
        return context.uri.resolve2('../home')



###########################################################################
# Register
###########################################################################

# Objects
register_object_class(Home)
register_object_class(Section)
register_object_class(MyWebApp)

# Skin
path = get_abspath(globals(), 'ui/webapp')
skin = Skin(path)
register_skin('webapp', skin)

# Website
register_website(MyWebApp)
