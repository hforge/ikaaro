# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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
from decimal import Decimal
from types import GeneratorType

# Import from itools
from itools.core import merge_dicts
from itools.csv import Property
from itools.datatypes import String, Tokens, Unicode
from itools.gettext import MSG
from itools.html import stream_to_str_as_html, xhtml_doctype
from itools.web import STLView
from itools.xml import XMLParser

# Import from ikaaro
from access import RoleAware
from config import Configuration
from folder import Folder
from resource_views import LoginView
from skins import UI, ui_path
from website_views import AboutView, ContactForm, CreditsView
from website_views import NotFoundView, ForbiddenView
from website_views import WebSite_NewInstance, UploadStatsView



class WebSite(RoleAware, Folder):

    class_id = 'WebSite'
    class_version = '20110606'
    class_title = MSG(u'Web Site')
    class_description = MSG(u'Create a new Web Site or Work Place.')
    class_icon16 = 'icons/16x16/website.png'
    class_icon48 = 'icons/48x48/website.png'
    class_skin = 'ui/aruni'
    class_views = Folder.class_views + ['control_panel']


    __fixed_handlers__ = ['skin', 'theme']


    def _get_resource(self, name):
        if name == 'ui':
            ui = UI(ui_path)
            return ui
        if name in ('users', 'users.metadata'):
            return self.parent._get_resource(name)
        return Folder._get_resource(self, name)


    class_schema = merge_dicts(
        Folder.class_schema,
        RoleAware.class_schema,
        # Metadata
        vhosts=String(source='metadata', multiple=True, indexed=True),
        contacts=Tokens(source='metadata'),
        emails_from_addr=String(source='metadata'),
        emails_signature=Unicode(source='metadata'),
        website_languages=Tokens(source='metadata', default=('en',)))

    # XXX Useful for the update method (i.e update_20100630)
    # To remove in ikaaro 0.70
    class_schema_extensible = True


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # Configuration
        self.make_resource('config', Configuration)


    ########################################################################
    # API
    ########################################################################
    def get_default_language(self):
        return self.get_property('website_languages')[0]


    def get_default_edit_languages(self):
        return [self.get_default_language()]


    def before_traverse(self, context, min=Decimal('0.000001'),
                        zero=Decimal('0.0')):
        # Set the language cookie if specified by the query.
        # NOTE We do it this way, instead of through a specific action,
        # to avoid redirections.
        language = context.get_form_value('language')
        if language is not None and language != '':
            context.set_cookie('language', language)

        # The default language (give a minimum weight)
        accept = context.accept_language
        default = self.get_default_language()
        if accept.get(default, zero) < min:
            accept.set(default, min)
        # User Profile (2.0)
        user = context.user
        if user is not None:
            language = user.get_property('user_language')
            if language is not None:
                accept.set(language, 2.0)
        # Cookie (2.5)
        language = context.get_cookie('language')
        if language is not None and language != '':
            accept.set(language, 2.5)


    def get_skin(self, context):
        # Back-Office
        hostname = context.uri.authority
        if hostname[:3] in ['bo.', 'bo-']:
            return self.get_resource('/ui/aruni')
        # Fron-Office
        return self.get_resource(self.class_skin)


    def after_traverse(self, context):
        body = context.entity
        is_str = type(body) is str
        is_xml = isinstance(body, (list, GeneratorType, XMLParser))
        if not is_str and not is_xml:
            return

        # If there is not a content type, just serialize the content
        if context.content_type:
            if is_xml:
                context.entity = stream_to_str_as_html(body)
            return

        # Standard page, wrap the content into the general template
        if is_str:
            body = XMLParser(body, doctype=xhtml_doctype)
        context.entity = self.get_skin(context).template(body)
        context.content_type = 'text/html; charset=UTF-8'


    def is_allowed_to_register(self):
        return self.get_security_policy() == 'community'


    #######################################################################
    # UI
    #######################################################################
    new_instance = WebSite_NewInstance()
    # Public views
    contact = ContactForm()
    about = AboutView()
    credits = CreditsView()
    license = STLView(access=True, title=MSG(u'License'),
                      template='/ui/root/license.xml')
    # Special
    forbidden = ForbiddenView()
    unauthorized = LoginView()
    not_found = NotFoundView()
    upload_stats = UploadStatsView()


    #######################################################################
    # Upgrade
    #######################################################################
    def update_20100430(self):
        vhosts = self.get_property('vhosts')
        if len(vhosts) == 1:
            vhosts = vhosts[0].split()
            if len(vhosts) > 1:
                self.set_property('vhosts', vhosts)


    def update_20100630(self):
        value = self.get_property('google-site-verification')
        self.set_property('google_site_verification', value)
        self.del_property('google-site-verification')


    def update_20100702(self):
        from theme import Theme

        theme = self.get_resource('theme', soft=True)
        if theme and isinstance(theme, Theme) is False:
            raise RuntimeError, 'A resource named theme already exists'

        # Theme folder
        theme = self.make_resource('theme', Theme, title={'en': u'Theme'})
        # Add home/contact links
        menu = theme.get_resource('menu/menu')
        menu.add_new_record({'path': '../../..',
                             'title': Property(u'Home', language='en'),
                             'target': '_top'})
        menu.add_new_record({'path': '../../../;contact',
                             'title': Property(u'Contact', language='en'),
                             'target': '_top'})


    def update_20110606(self):
        self.make_resource('config', Configuration)
        # TODO
