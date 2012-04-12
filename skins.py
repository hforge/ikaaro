# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from copy import deepcopy
from os.path import isfile

# Import from itools
from itools.core import get_abspath
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.stl import stl
from itools.web import get_context, ERROR, INFO

# Import from ikaaro
from context import register_ui
from folder import Folder
from views import get_view_scripts
from skins_views import LanguagesTemplate, LocationTemplate


class Skin(object):

    class_title = MSG(u'Skin')
    class_icon16 = 'icons/16x16/skin.png'
    class_icon48 = 'icons/48x48/skin.png'

    # User Interface widgets
    languages_template = LanguagesTemplate
    location_template = LocationTemplate


    def __init__(self, key):
        self.key = key


    #######################################################################
    # HTML head
    #######################################################################
    def get_template_title(self, context):
        """Return the title to give to the template document.
        """
        here = context.resource
        root = context.root
        root_title = root.get_title()

        # Choose the template
        if not root.is_allowed_to_view(context.user, here):
            return ''
        elif root is here:
            template = MSG(u"{view_title} - {root_title}")
            here_title = None
        else:
            template = MSG(u"{here_title} - {view_title} - {root_title}")
            here_title = here.get_title()

        # The view
        view_title = context.view.get_title(context)

        # Ok
        return template.gettext(root_title=root_title, here_title=here_title,
                                view_title=view_title)


    def _get_theme_file(self, context, name):
        theme = context.database.get_resource('/config/theme')
        if context.root.is_allowed_to_view(context.user, theme):
            value = theme.get_value(name)
            if value:
                return value

        return None


    def get_styles(self, context):
        # Generic
        styles = ['/ui/bo.css']

        # Skin
        if isfile('%s/style.css' % self.key):
            styles.append('%s/style.css' % self.base_path)

        # View
        get_styles = getattr(context.view, 'get_styles', None)
        if get_styles is None:
            extra = getattr(context.view, 'styles', [])
        else:
            extra = get_styles(context)
        styles.extend(extra)

        # Database style
        if self._get_theme_file(context, 'style'):
            styles.append(
                '/config/theme/;get_file?name=style&mimetype=text/css')

        # Ok
        return styles


    def get_scripts(self, context):
        scripts = [
            '/ui/jquery.js',
            '/ui/javascript.js']

        # This skin's JavaScript
        if isfile('%s/javascript.js' % self.key):
            scripts.append('%s/javascript.js' % self.base_path)

        # View
        for script in get_view_scripts(context.view, context):
            if script not in scripts:
                scripts.append(script)

        # Ok
        return scripts


    def get_meta_tags(self, context):
        """Return a list of dict with meta tags to give to the template
        document.
        """
        here = context.resource
        root = context.root

        meta = []
        # Set description
        try:
            property = here.get_property('description')
        except ValueError:
            pass
        else:
            if property:
                meta.append({
                    'name': 'description',
                    'lang': property.get_parameter('lang'),
                    'content': property.value})

        # Set keywords for all languages
        for language in root.get_value('website_languages'):
            try:
                value = here.get_value('subject', language)
            except ValueError:
                continue
            if value is None:
                continue
            value = value.strip()
            if value:
                meta.append({'name': 'keywords', 'lang': language,
                             'content': value})

        # Search engine optimization
        seo = root.get_resource('config/seo')
        for key, meta_name in [
            ('google_site_verification', 'google-site-verification'),
            ('yahoo_site_verification', 'y_key'),
            ('bing_site_verification', 'msvalidate.01')]:
            verification_key = seo.get_value(key)
            if verification_key:
                meta.append({'name': meta_name,
                             'lang': None,
                             'content': verification_key})

        # View
        # meta are defined as a tuple (name, content, language)
        extra_meta = getattr(context.view, 'meta', [])
        for (name, content, lang) in extra_meta:
            meta.append({'name': name, 'content': content, 'lang': lang})

        return meta


    def get_favicon(self, context):
        # Case 1: from the database
        favicon = self._get_theme_file(context, 'favicon')
        if favicon:
            favicon_href = '/config/theme/;get_file?name=favicon'
            favicon_type = favicon.get_mimetype()
            return favicon_href, favicon_type

        # Case 2: from the skin
        favicon = '%s/favicon.ico' % self.base_path
        if context.get_template(favicon):
            return (favicon, 'image/x-icon')

        # Case 3: default
        return ('/ui/favicon.ico', 'image/x-icon')


    #######################################################################
    # Authenticated user
    #######################################################################
    def get_usermenu(self, context):
        """Return a dict {'name': ..., 'title': ..., 'home': ...}
        """
        here = context.resource
        base_path = context.get_link(here)

        # Case 1: Anonymous
        user = context.user
        if user is None:
            return [{'href': '%s/;login' % base_path,
                     'title': MSG(u'Sign in'),
                     'id': 'links-menu-login'}]

        # Case 2: Authenticated
        usermenu = [
            # Home
            {'href': '/users/%s' % user.name,
             'title': user.get_title(),
             'id': 'links-menu-profile'},
            # Logout
            {'href': '%s/;logout' % base_path,
             'title': MSG(u'Log out'),
             'id': 'links-menu-logout'}]

        # Add content
        container = here
        if isinstance(here, Folder) is False:
            container = here.parent
        view = container.get_view('new_resource')
        if context.is_access_allowed(container, view):
            usermenu.append({
                'href': '%s/;new_resource' % context.get_link(container),
                'title': MSG(u'Add content'),
                'id': 'links-menu-new'})

        # Configuration
        config = here.get_resource('/config')
        if context.root.is_allowed_to_view(user, config):
            usermenu.append({
                'href': '/config',
                'title': MSG(u'Configuration'),
                'id': 'links-menu-configuration'})

        return usermenu


    #######################################################################
    # Body
    #######################################################################
    def _get_page_title(self, context):
        resource = context.resource
        view = context.view

        # Not allowed to view resource
        root = context.root
        if not root.is_allowed_to_view(context.user, resource):
            return ''

        # Page title
        try:
            get_page_title = view.get_page_title
        except AttributeError:
            return resource.get_page_title()

        return get_page_title(resource, context)


    def get_messages(self, context):
        """Return the message string of the last action.
        A list of messages is supported.
        """
        # Text
        if context.message is not None:
            messages = context.message
        elif 'error' in context.uri.query:
            messages = ERROR(context.get_query_value('error', type=Unicode))
        elif 'info' in context.uri.query:
            messages = INFO(context.get_query_value('info', type=Unicode))
        # XXX For backwards compatibility
        elif 'message' in context.uri.query:
            messages = INFO(context.get_query_value('message', type=Unicode))
        else:
            return None

        # Multiple messages:
        if not isinstance(messages, list):
            messages = [messages]

        messages_ns = []
        for message in messages:
            css_class = getattr(message, 'css', 'info')
            messages_ns.append({'message': message, 'class': css_class})

        namespace = {'messages': messages_ns}

        template = context.get_template('/ui/aruni/message.xml')
        return stl(template, namespace)


    def _get_context_menus(self, context):
        resource = context.resource
        # Resource
        for menu in resource.get_context_menus():
            menu = menu(resource=resource, context=context)
            yield menu.render()

        # View
        get_context_menus = getattr(context.view, 'get_context_menus', None)
        if get_context_menus is None:
            menus = getattr(context.view, 'context_menus', [])
        else:
            menus = get_context_menus()

        for menu in menus:
            menu = menu(resource=resource, context=context)
            yield menu.render()


    def get_footer(self, context):
        footer = context.root.get_resource('config/footer')
        return footer.get_html_data()


    def get_menu_namespace(self, context):
        menu = context.root.get_resource('config/menu')
        return menu.get_menu_namespace(context)


    #######################################################################
    # Main
    #######################################################################
    def build_namespace(self, context):
        # Context menus
        context_menus = self._get_context_menus(context)
        context_menus = list(context_menus)

        # The favicon.ico
        favicon_href, favicon_type = self.get_favicon(context)

        # Logo
        logo = self._get_theme_file(context, 'logo')
        logo_href = '/config/theme/;get_file?name=logo' if logo else None

        # The document language
        languages = context.root.get_value('website_languages')
        language = context.accept_language.select_language(languages)

        # The base URI
        uri = context.uri
        if uri.path and not context.view_name and not uri.path.endswith_slash:
            uri = deepcopy(uri)
            uri.path.endswith_slash = True

        # Location template
        location_template = self.location_template
        if location_template:
            location_template = location_template(context=context)

        # Ok
        return {
            # HTML head
            'language': language,
            'title': self.get_template_title(context),
            'base_uri': str(uri),
            'canonical_uri': context.view.get_canonical_uri(context),
            'styles': self.get_styles(context),
            'scripts': self.get_scripts(context),
            'meta_tags': self.get_meta_tags(context),
            'favicon_href': favicon_href,
            'favicon_type': favicon_type,
            # logo
            'logo_href': logo_href,
            # Usermenu (the links at the top)
            'usermenu': self.get_usermenu(context),
            # menu
            'menu': self.get_menu_namespace(context),
            # Location & Views
            'location': location_template,
            'languages': self.languages_template(context=context),
            # Body
            'page_title': self._get_page_title(context),
            'message': self.get_messages(context),
            'context_menus': context_menus,
            # Footer
            'footer': self.get_footer(context),
        }


    def get_template(self, context):
        paths = [
            '%s/template.xhtml' % self.base_path,
            '/ui/aruni/template.xhtml']
        for path in paths:
            template = context.get_template(path)
            if template:
                return path, template

        raise ValueError, 'XXX'


    def template(self, content):
        context = get_context()
        # Build the namespace
        namespace = self.build_namespace(context)
        namespace['body'] = content

        # Set the encoding to UTF-8
        context.content_type = 'text/html; charset=UTF-8'

        # Load the template
        prefix, handler = self.get_template(context)

        # Build the output
        s = ['<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"\n'
             '  "http://www.w3.org/TR/html4/strict.dtd">']
        # STL
        data = stl(handler, namespace, prefix=prefix, mode='html')
        s.append(data)

        return ''.join(s)


###########################################################################
# Specific Skin for popup
###########################################################################
class FancyboxSkin(Skin):

    location_template = None



#############################################################################
# The folder "/ui"
#############################################################################

skin_registry = {}
def register_skin(name, skin):
    if isinstance(skin, str):
        skin = Skin(skin)
    skin.base_path = '/ui/%s' % name
    skin_registry[name] = skin
    register_ui('/ui/%s/' % name, skin.key)


# Register the built-in skins
ui_path = get_abspath('ui')
register_skin('aruni', '%s/aruni' % ui_path)
register_skin('popup', '%s/popup' % ui_path)
register_skin('fancybox', FancyboxSkin('%s/fancybox' % ui_path))
register_ui('/ui/', ui_path)
