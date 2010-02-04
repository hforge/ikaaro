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

# Import from itools
from itools.core import merge_dicts
from itools.datatypes import Boolean, String, Tokens, Unicode
from itools.gettext import MSG
from itools.web import stl_view, VirtualRoot

# Import from ikaaro
from calendar.views import MonthlyView, WeeklyView, DailyView
from control_panel import ControlPanel, CPBrokenLinks, CPEditContactOptions
from control_panel import CPEditLanguages, CPEditSecurityPolicy
from control_panel import CPEditVirtualHosts, CPEditSEO
from folder_views import Folder_Orphans
from registry import register_document_type
from resource_views import LoginView
from skins import Skin
from views_new import ProxyNewInstance
from website_views import AboutView, ContactForm, CreditsView
from website_views import ForgottenPasswordForm, RegisterForm
from website_views import NotFoundView, ForbiddenView, InternalServerError
from workspace import Workspace



class WebSite(VirtualRoot, Workspace):

    class_id = 'WebSite'
    class_title = MSG(u'Web Site')
    class_description = MSG(u'Create a new Web Site or Work Place.')
    class_icon16 = 'icons/16x16/website.png'
    class_icon48 = 'icons/48x48/website.png'
    class_skin = 'ui/aruni'
    class_views = ['view', 'list', 'table', 'gallery', 'month', 'week',
                   'edit', 'backlinks', 'control_panel', 'commit_log']
    class_control_panel = [
        'edit_security_policy', 'edit_virtual_hosts', 'edit_seo',
        'edit_languages', 'edit_contact_options', 'broken_links', 'orphans']


    __fixed_handlers__ = ['index', 'skin', 'users']


    class_schema = merge_dicts(
        Workspace.class_schema,
        # Metadata
        vhosts=String(source='metadata', multiple=True, indexed=True),
        contacts=Tokens(source='metadata'),
        emails_from_addr=String(source='metadata'),
        emails_signature=Unicode(source='metadata'),
        google_site_verification=String(source='metadata'),
        yahoo_site_verification=String(source='metadata'),
        bing_site_verification=String(source='metadata'),
        website_languages=Tokens(source='metadata', default=('en',)),
        website_is_open=Boolean(source='metadata'))


    ########################################################################
    # API
    ########################################################################
    def get_default_language(self):
        return self.get_value('website_languages')[0]


    def is_allowed_to_register(self, user, resource):
        return self.get_property('website_is_open')


    #######################################################################
    # HTTP stuff
    #######################################################################
    def get_skin(self):
        return Skin

    # Views for error conditions
    http_forbidden = ForbiddenView
    http_unauthorized = LoginView
    http_not_found = NotFoundView
    http_internal_server_error = InternalServerError


    #######################################################################
    # UI
    #######################################################################
    new_instance = ProxyNewInstance
    # Control Panel
    control_panel = ControlPanel
    edit_virtual_hosts = CPEditVirtualHosts
    edit_security_policy = CPEditSecurityPolicy
    edit_seo = CPEditSEO
    edit_contact_options = CPEditContactOptions
    edit_languages = CPEditLanguages
    broken_links = CPBrokenLinks
    orphans = Folder_Orphans
    # Register / Login
    register = RegisterForm
    forgotten_password = ForgottenPasswordForm
    # Public views
    contact = ContactForm
    about = AboutView
    credits = CreditsView
    license = stl_view(access=True, view_title=MSG(u'License'),
                       template='root/license.xml')

    # Calendar views
    month = MonthlyView
    week = WeeklyView
    day = DailyView


###########################################################################
# Register
###########################################################################
register_document_type(WebSite, WebSite.class_id)
