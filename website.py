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
from itools.database import AndQuery, PhraseQuery
from itools.datatypes import String, Tokens
from itools.gettext import MSG
from itools.html import stream_to_str_as_html, xhtml_doctype
from itools.web import AccessControl, STLView
from itools.xml import XMLParser

# Import from ikaaro
from autoform import MultilineWidget
from config import Configuration
from folder import Folder
from config_access import SavedSearch_Content
from config_register import RegisterForm
from registry import get_resource_class
from resource_views import LoginView
from skins import skin_registry
from user import UserFolder
from website_views import AboutView, ContactForm, CreditsView
from website_views import NotFoundView, ForbiddenView
from website_views import WebSite_NewInstance, UploadStatsView
from workflow import WorkflowAware



###########################################################################
# Utility
###########################################################################
def is_admin(user, resource):
    if user is None or resource is None:
        return False

    if (resource.get_site_root().get_abspath() !=
        user.get_site_root().get_abspath()):
        return False

    return 'admins' in user.get_property('groups')



###########################################################################
# Resource
###########################################################################
class WebSite(AccessControl, Folder):

    class_id = 'WebSite'
    class_version = '20110606'
    class_title = MSG(u'Web Site')
    class_description = MSG(u'Create a new Web Site or Work Place.')
    class_icon16 = 'icons/16x16/website.png'
    class_icon48 = 'icons/48x48/website.png'
    class_skin = 'aruni'
    class_views = Folder.class_views + ['control_panel']


    class_schema = merge_dicts(
        Folder.class_schema,
        # Metadata
        vhosts=String(source='metadata', multiple=True, indexed=True,
                      title=MSG(u'Domain names'),
                      widget=MultilineWidget),
        website_languages=Tokens(source='metadata', default=('en',)))

    # XXX Useful for the update method (i.e update_20100630)
    # To remove in ikaaro 0.71
    class_schema_extensible = True

    is_content = True


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # Users
        self.make_resource('users', UserFolder, title={'en': u'Users'})
        # Configuration
        config = self.make_resource('config', Configuration,
                                    title={'en': u'Configuration'})
        # Saved searches
        searches = config.get_resource('searches')
        items = [('any-content', None),
                 ('public-content', ['public']),
                 ('private-content', ['private', 'pending'])]
        for name, value in items:
            search = searches.make_resource(name, SavedSearch_Content)
            search.set_property('search_workflow_state', value)

        # Permissions
        permissions = [
            # Authenticated users can see any content
            ('authenticated', 'view', 'any-content'),
            # Members can add new content, edit private content and request
            # publication
            ('members', 'add', 'any-content'),
            ('members', 'edit', 'private-content'),
            ('members', 'wf_request', None),
            # Reviewers can add new content, edit any content and publish
            ('reviewers', 'add', 'any-content'),
            ('reviewers', 'edit', 'any-content'),
            ('reviewers', 'wf_request', 'any-content'),
            ('reviewers', 'wf_publish', 'any-content'),
            # Admins can do anything
            ('admins', 'view', None),
            ('admins', 'edit', None),
            ('admins', 'add', None),
            ('admins', 'wf_request', None),
            ('admins', 'wf_publish', None),
        ]
        access = config.get_resource('access').handler
        for group, permission, resources in permissions:
            access.add_record({'group': group, 'permission': permission,
                               'resources': resources})


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
    def make_user(self, loginname=None, password=None):
        # Create the user
        users = self.get_resource('/users')
        user_id = users.get_next_user_id()
        cls = get_resource_class('user')
        user = users.make_resource(user_id, cls)

        # Set login name and paswword
        if loginname is not None:
            user.set_property(user.login_name_property, loginname)
        if password is not None:
            user.set_password(password)

        # Return the user
        return user


    def get_groups(self):
        return self.get_names('config/groups')


    def get_members(self):
        return set(self.get_names('users'))


    def is_allowed_to_register(self, user, resource):
        if user:
            return False
        return self.get_resource('config/register').get_property('is_open')


    def is_admin(self, user, resource):
        return is_admin(user, resource)


    def is_allowed_to_view(self, user, resource):
        access = self.get_resource('config/access')
        return access.has_permission(user, 'view', resource)


    def is_allowed_to_edit(self, user, resource):
        access = self.get_resource('config/access')
        return access.has_permission(user, 'edit', resource)


    def is_allowed_to_add(self, user, resource):
        access = self.get_resource('config/access')
        return access.has_permission(user, 'add', resource)


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


    # By default all other change operations (add, remove, copy, etc.)
    # are equivalent to "edit".
    def is_allowed_to_put(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_remove(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_copy(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_move(self, user, resource):
        return self.is_allowed_to_edit(user, resource)


    def is_allowed_to_publish(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'publish')


    def is_allowed_to_retire(self, user, resource):
        return self.is_allowed_to_trans(user, resource, 'retire')


    def is_allowed_to_view_folder(self, user, resource):
        index = resource.get_resource('index', soft=True)
        if index is None:
            return False
        return self.is_allowed_to_view(user, index)


    def get_user(self, name):
        return self.get_resource('users/%s' % name, soft=True)


    def get_user_from_login(self, username):
        """Return the user identified by its unique e-mail or username, or
        return None.
        """
        # Search the user by username (login name)
        query = PhraseQuery('username', username)
        results = self.search_users(query)
        n = len(results)
        if n == 0:
            return None
        if n > 1:
            error = 'There are %s users in the database identified as "%s"'
            raise ValueError, error % (n, username)
        # Get the user
        brain = results.get_documents()[0]
        return self.get_user(brain.name)


    def search_users(self, query):
        base_path = str(self.get_resource('users').get_abspath())
        query = AndQuery(PhraseQuery('parent_paths', base_path), query)
        return self.get_root().search(query)


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
