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
from decimal import Decimal
from types import FunctionType, MethodType

# Import from itools
from itools.datatypes import Unicode
from itools.fs import lfs
from itools.gettext import MSG
from itools.stl import stl
from itools.web import ERROR, INFO, STLForm

# Import from ikaaro
from skins_views import LanguagesTemplate, LocationTemplate


class Skin(STLForm):

    class_title = MSG(u'Skin')
    class_icon16 = 'icons/16x16/skin.png'
    class_icon48 = 'icons/48x48/skin.png'
    template = 'aruni/template.xhtml'
    styles = ['/ui/aruni/style.css']
    scripts = []

    # User Interface widgets
    languages_template = LanguagesTemplate
    location_template = LocationTemplate


    #######################################################################
    # HTML head
    #######################################################################
    def get_template_title(self, context):
        """Return the title to give to the template document.
        """
        here = context.resource
        root = here.get_site_root()
        root_title = root.get_title()

        # Choose the template
        if root is here:
            template = MSG(u"{root_title} - {view_title}")
            here_title = None
        else:
            template = MSG(u"{root_title} - {here_title} - {view_title}")
            here_title = here.get_title()

        # The view
        view_title = context.view.get_title(context)
        if type(view_title) is MSG:
            view_title = view_title.gettext()

        # Ok
        return template.gettext(root_title=root_title, here_title=here_title,
                                view_title=view_title)


    def get_styles(self, context):
        # Generic
        styles = [
            '/ui/bo.css',
            '/ui/js_calendar/calendar-aruni.css',
            '/ui/table/style.css']

        # Skin
        styles.extend(self.styles)

        # View
        get_styles = getattr(context.view, 'get_styles', None)
        if get_styles is None:
            extra = getattr(context.view, 'styles', [])
        else:
            extra = get_styles(context)
        styles.extend(extra)

        # Ok
        return styles


    def get_scripts(self, context):
        scripts = [
            '/ui/jquery.js',
            '/ui/javascript.js']

        # Calendar (http://code.google.com/p/dyndatetime/)
        scripts.append('/ui/js_calendar/jquery.dynDateTime.pack.js')
        languages = [
            'af', 'al', 'bg', 'br', 'ca', 'da', 'de', 'du', 'el', 'en', 'es',
            'fi', 'fr', 'hr', 'hu', 'it', 'jp', 'ko', 'lt', 'lv', 'nl', 'no',
            'pl', 'pt', 'ro', 'ru', 'si', 'sk', 'sp', 'sv', 'tr', 'zh']
        accept = context.accept_language
        language = accept.select_language(languages)
        if language is None:
            language = 'en'
        scripts.append('/ui/js_calendar/lang/calendar-%s.js' % language)

        # This skin's JavaScript
        scripts.extend(self.scripts)

        # View
        get_scripts = getattr(context.view, 'get_scripts', None)
        if get_scripts is None:
            extra = getattr(context.view, 'scripts', [])
        else:
            extra = get_scripts(context)
        scripts.extend(extra)

        # Ok
        return scripts


    def get_meta_tags(self, context):
        """Return a list of dict with meta tags to give to the template
        document.
        """
        here = context.resource
        root = here.get_site_root()

        meta = []
        # Set description
        try:
            property = here._get_property('description')
        except ValueError:
            pass
        else:
            if property:
                meta.append({
                    'name': 'description',
                    'lang': property.parameters['lang'],
                    'content': property.value})

        # Set keywords for all languages
        for language in root.get_property('website_languages'):
            try:
                value = here.get_property('subject', language)
            except ValueError:
                continue
            if value is None:
                continue
            value = value.strip()
            if value:
                meta.append({'name': 'keywords', 'lang': language,
                             'content': value})

        # Search engine optimization
        for key, meta_name in [
            ('google-site-verification', 'google-site-verification'),
            ('yahoo_site_verification', 'y_key'),
            ('bing_site_verification', 'msvalidate.01')]:
            verification_key = root.get_property(key)
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


    #######################################################################
    # Authenticated user
    #######################################################################
    def get_user_menu(self, context):
        """Return a dict {user_icon, user, joinisopen}.
        """
        user = context.user

        if user is None:
            host = context.host
            joinisopen = host.is_allowed_to_register(user, host)
            return {'info': None, 'joinisopen': joinisopen}

        home = '/users/%s' % user.name
        info = {'name': user.name, 'title': user.get_title(),
                'home': home}
        return {'info': info, 'joinisopen': False}


    #######################################################################
    # Body
    #######################################################################
    def _get_page_title(self, context):
        resource = context.resource
        view = context.view

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
        elif 'error' in context.query:
            messages = ERROR(context.get_query_value('error', type=Unicode))
        elif 'info' in context.query:
            messages = INFO(context.get_query_value('info', type=Unicode))
        # XXX For backwards compatibility
        elif 'message' in context.query:
            messages = INFO(context.get_query_value('message', type=Unicode))
        else:
            return None

        # Multiple messages:
        if not isinstance(messages, list):
            messages = [messages]

        messages_ns = []
        for message in messages:
            css_class = 'error' if isinstance(message, ERROR) else 'info'
            messages_ns.append({'message': message, 'class': css_class})

        namespace = {'messages': messages_ns}

        template = context.root.get_resource('/ui/aruni/message.xml')
        return stl(template, namespace)


    def _get_context_menus(self, context):
        resource = context.resource
        # Resource
        for menu in resource.get_context_menus():
            yield menu.render(resource, context)
        # View
        menus = getattr(context.view, 'context_menus', [])
        for menu in menus:
            yield menu.render(resource, context)


    #######################################################################
    # Main
    #######################################################################
    def build_namespace(self, context):
        context_menus = self._get_context_menus(context)
        context_menus = list(context_menus)

        # The favicon.ico
        host = context.host
        resource = host.get_resource('favicon', soft=True)
        if resource:
            favicon_href = '/favicon/;download'
            favicon_type = resource.metadata.format
        else:
            favicon_href = '/ui/favicon.ico'
            favicon_type = 'image/x-icon'

        # The document language
        here = context.resource
        languages = here.get_site_root().get_property('website_languages')
        language = context.accept_language.select_language(languages)

        # The base URI
        path = context.path
        if path and not context.view_name and not path.endswith_slash:
            path = deepcopy(path)
            path.endswith_slash = True
        else:
            uri = context.uri

        # In case of UI objects, fallback to site root
        base_path = context.get_link(here)

        # The view
        view = context.view

        return {
            # HTML head
            'language': language,
            'title': self.get_template_title(context),
            'base_uri': str(uri),
            'canonical_uri': view.get_canonical_uri(context),
            'styles': self.get_styles(context),
            'scripts': self.get_scripts(context),
            'meta_tags': self.get_meta_tags(context),
            # Log in/out
            'login': '%s/;login' % base_path,
            'logout': '%s/;logout' % base_path,
            # User
            'user': self.get_user_menu(context),
            # Location & Views
            'location': self.location_template(context),
            'languages': self.languages_template(context),
            # Body
            'page_title': self._get_page_title(context),
            'message': self.get_messages(context),
            'context_menus': context_menus,
            # favicon
            'favicon_href': favicon_href,
            'favicon_type': favicon_type,
        }


    def find_language(self, resource, context, min=Decimal('0.000001'),
                      zero=Decimal('0.0')):
        # Set the language cookie if specified by the query.
        # NOTE We do it this way, instead of through a specific action, to
        # avoid redirections.
        language = context.get_query_value('language')
        if language is not None:
            context.set_cookie('language', language)

        # The default language (give a minimum weight)
        accept = context.accept_language
        default = resource.get_default_language()
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
        if language is not None:
            accept.set(language, 2.5)


    def render(self, content, context):
        resource = context.resource
        self.find_language(resource, context)

        # Build the namespace
        namespace = self.build_namespace(context)
        namespace['body'] = content

        # Set the encoding to UTF-8
        context.content_type = 'text/html; charset=UTF-8'

        # Load the template
        handler = self.get_template(resource, context)

        # Build the output
        s = ['<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"\n'
             '  "http://www.w3.org/TR/html4/strict.dtd">']
        # STL
#        prefix = handler.get_abspath()
        data = stl(handler, namespace, mode='html')#prefix=prefix, mode='html')
        s.append(data)

        return ''.join(s)


    def POST(self, resource, context):
        self.find_language(resource, context)
        entity = context.method(context.resource, context)

        # Most often a post method will render a page
        if isinstance(entity, (FunctionType, MethodType)):
            context.method = entity
            return self.GET(resource, context)

        return entity

