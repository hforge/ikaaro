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
from itools.database import AndQuery, OrQuery, PhraseQuery
from itools.datatypes import String, Tokens
from itools.gettext import MSG
from itools.html import stream_to_str_as_html, xhtml_doctype
from itools.web import STLView
from itools.xml import XMLParser

# Import from ikaaro
from access import AccessControl
from config import Configuration
from folder import Folder
from config_register import RegisterForm
from registry import get_resource_class
from resource_views import LoginView
from skins import skin_registry
from website_views import AboutView, ContactForm, CreditsView
from website_views import NotFoundView, ForbiddenView
from website_views import WebSite_NewInstance, UploadStatsView
from workflow import WorkflowAware



class WebSite(AccessControl, Folder):

    class_id = 'WebSite'
    class_version = '20110606'
    class_title = MSG(u'Web Site')
    class_description = MSG(u'Create a new Web Site or Work Place.')
    class_icon16 = 'icons/16x16/website.png'
    class_icon48 = 'icons/48x48/website.png'
    class_skin = 'aruni'
    class_views = Folder.class_views + ['control_panel']


    def _get_resource(self, name):
        if name in ('users', 'users.metadata'):
            return self.parent._get_resource(name)
        return Folder._get_resource(self, name)


    class_schema = merge_dicts(
        Folder.class_schema,
        # Metadata
        vhosts=String(source='metadata', multiple=True, indexed=True),
        website_languages=Tokens(source='metadata', default=('en',)))

    # XXX Useful for the update method (i.e update_20100630)
    # To remove in ikaaro 0.70
    class_schema_extensible = True


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # Configuration
        config = self.make_resource('config', Configuration,
                                    title={'en': u'Configuration'})
        # Permissions
        permissions = {
            'view_public': ['authenticated'],
            'view_private': ['authenticated'],
            'edit_public': ['reviewers', 'admins'],
            'edit_private': ['members', 'reviewers', 'admins'],
            'wf_publish': ['reviewers', 'admins'],
            'wf_request': ['members', 'reviewers', 'admins'],
            'config': ['admins']}
        access = config.get_resource('access').handler
        for permission, groups in permissions.items():
            for group in groups:
                access.add_record({'permission': permission, 'group': group})


    def make_resource(self, name, cls, **kw):
        if name == 'ui':
            raise ValueError, 'cannot add a resource with the name "ui"'
        return Folder.make_resource(self, name, cls, **kw)


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
            return skin_registry['aruni']
        # Fron-Office
        return skin_registry[self.class_skin]


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


    #######################################################################
    # Access control
    #######################################################################
    def is_allowed_to_register(self, user, resource):
        if user:
            return False
        return self.get_resource('config/register').get_property('is_open')


    def make_user(self, email=None, password=None):
        # Create the user
        users = self.get_resource('/users')
        user_id = users.get_next_user_id()
        cls = get_resource_class('user')
        user = users.make_resource(user_id, cls)

        # Set the email and paswword
        if email is not None:
            user.set_property('email', email)
        if password is not None:
            user.set_password(password)

        # Attach to website
        self.attach_user(user)

        # Return the user
        return user


    def attach_user(self, user, group=None):
        website_id = str(self.get_abspath())
        user.set_property('websites', website_id)
        # Option: attach group
        if group is not None:
            group = self.get_resource('config/groups/%s' % group)
            group_id = str(group.get_abspath())
            user.set_property('groups', group_id)


    def get_groups(self):
        return [
            str(x.get_abspath())
            for x in self.get_resources('config/groups') ]


    def get_members(self):
        groups = self.get_groups()
        query = AndQuery(
            PhraseQuery('format', 'user'),
            OrQuery(* [ PhraseQuery('groups', x) for x in groups ]))

        results = self.get_root().search(query)
        return set([ x.name for x in results.get_documents() ])


    def has_user_role(self, user, *group_names):
        user_groups = set(user.get_property('groups'))

        path = str(self.get_resource('config/groups').get_abspath()) + '/'
        for group_name in group_names:
            group_id = path + group_name
            if group_id in user_groups:
                return True

        return False


    def is_allowed_to_view(self, user, resource):
        # 1. Permission
        state = getattr(resource, 'workflow_state', 'public')
        permission = 'view_public' if state == 'public' else 'view_private'
        # 2. Access
        access = self.get_resource('config/access')
        return access.has_permission(user, permission)


    def is_allowed_to_edit(self, user, resource):
        # 1. Permission
        state = getattr(resource, 'workflow_state', 'private')
        permission = 'edit_public' if state == 'public' else 'edit_private'
        # 2. Access
        access = self.get_resource('config/access')
        return access.has_permission(user, permission)


    def is_allowed_to_trans(self, user, resource, name):
        if not isinstance(resource, WorkflowAware):
            return False

        # 1. Permission
        if name in ('publish', 'retire'):
            permission = 'wf_publish'
        elif name in ('request', 'unrequest'):
            permission = 'wf_request'

        # 2. Access
        access = self.get_resource('config/access')
        return access.has_permission(user, permission)


    #######################################################################
    # UI
    #######################################################################
    new_instance = WebSite_NewInstance()
    register = RegisterForm()
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
        from config_theme import Theme

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
