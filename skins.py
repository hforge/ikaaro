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

# Import from itools
from itools.core import get_abspath
from itools.datatypes import Unicode
from itools.gettext import MSG
from itools.handlers import File, Folder, Image
from itools.http import NotFound
from itools.i18n import has_language
from itools.stl import stl
from itools.uri import Path
from itools.web import get_context, BaseView, ERROR, INFO
from itools.xmlfile import XMLFile

# Import from ikaaro
from resource_ import IResource
from skins_views import LanguagesTemplate, LocationTemplate



class FileGET(BaseView):

    access = True


    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        response = context.response
        response.set_header('Content-Type', resource.get_mimetype())
        return resource.to_str()



class UIFile(IResource, File):

    clone_exclude = File.clone_exclude | frozenset(['parent', 'name'])


    download = FileGET()

    def get_view(self, name, query=None):
        if name is None:
            return self.download
        raise NotFound



class UIImage(Image, UIFile):
    pass



class UITemplate(UIFile, XMLFile):
    pass



map = {
    'application/xml': UITemplate,
    'application/xhtml+xml': UITemplate,
    'text/xml': UITemplate,
    'image/png': UIImage,
    'image/jpeg': UIImage,
}



class UIFolder(IResource, Folder):

    class_title = MSG(u'UI')
    class_icon48 = 'icons/48x48/folder.png'


    def _get_names(self):
        # FIXME May not be the right implementation
        return self.get_handler_names()


    def _get_resource(self, name):
        if self.has_handler(name):
            handler = self.get_handler(name)
        else:
            name = '%s.' % name
            n = len(name)
            languages = []
            for x in self.get_handler_names():
                if x[:n] == name:
                    language = x[n:]
                    if has_language(language):
                        languages.append(language)

            if not languages:
                return None

            # Get the best variant
            context = get_context()
            if context is None:
                language = None
            else:
                accept = context.accept_language
                language = accept.select_language(languages)

            # By default use whatever variant
            # (XXX we need a way to define the default)
            if language is None:
                language = languages[0]
            handler = self.get_handler('%s%s' % (name, language))

        if isinstance(handler, Folder):
            handler = UIFolder(handler.uri)
        else:
            format = handler.get_mimetype()
            cls = map.get(format, UIFile)
            handler = cls(handler.uri)
        handler.database = self.database
        return handler



class Skin(UIFolder):

    class_title = MSG(u'Skin')
    class_icon16 = 'icons/16x16/skin.png'
    class_icon48 = 'icons/48x48/skin.png'

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
        styles = [
            # BackOffice style
            '/ui/bo.css',
            # Calendar JS Widget (http://dynarch.com/mishoo/calendar.epl)
            '/ui/js_calendar/calendar-aruni.css',
            # Table
            '/ui/table/style.css']

        # This skin's style
        if self.has_handler('style.css'):
            styles.append('%s/style.css' % self.get_canonical_path())
        # Dynamic styles
        for style in context.styles:
            styles.append(style)

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
        if self.has_handler('javascript.js'):
            scripts.append('%s/javascript.js' % self.get_canonical_path())

        # Dynamic scripts
        for script in context.scripts:
            scripts.append(script)

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
            value, language = here.get_property_and_language('description')
        except ValueError:
            pass
        else:
            if value:
                meta.append({'name': 'description', 'lang': language,
                             'content': value})

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

        return meta


    #######################################################################
    # Authenticated user
    #######################################################################
    def get_user_menu(self, context):
        """Return a dict {user_icon, user, joinisopen}.
        """
        user = context.user

        if user is None:
            site_root = context.site_root
            joinisopen = site_root.is_allowed_to_register(user, site_root)
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
        site_root = context.site_root
        resource = site_root.get_resource('favicon', soft=True)
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
        uri = context.uri
        if uri.path and not context.view_name and not uri.path.endswith_slash:
            uri = deepcopy(uri)
            uri.path.endswith_slash = True

        # In case of UI objects, fallback to site root
        if isinstance(here, (UIFile, UIFolder)):
            base_path = ''
        else:
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


    def get_template(self):
        template = self.get_resource('template.xhtml', soft=True)
        if template is not None:
            return template

        # Default: aruni
        return self.get_resource('/ui/aruni/template.xhtml')


    def template(self, content):
        context = get_context()
        # Build the namespace
        namespace = self.build_namespace(context)
        namespace['body'] = content

        # Set the encoding to UTF-8
        context.response.set_header('Content-Type', 'text/html; charset=UTF-8')

        # Load the template
        handler = self.get_template()

        # Build the output
        s = ['<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"\n'
             '  "http://www.w3.org/TR/html4/strict.dtd">']
        # STL
        prefix = handler.get_abspath()
        data = stl(handler, namespace, prefix=prefix, mode='html')
        s.append(data)

        return ''.join(s)



#############################################################################
# The folder "/ui"
#############################################################################

skin_registry = {}
def register_skin(name, skin):
    if isinstance(skin, str):
        skin = Skin(skin)
    skin_registry[name] = skin


# Register the built-in skins
ui_path = get_abspath('ui')
register_skin('aruni', '%s/aruni' % ui_path)


class UI(UIFolder):

    def _get_resource(self, name):
        if name in skin_registry:
            skin = skin_registry[name]
            skin.database = self.database
            return skin
        return UIFolder._get_resource(self, name)


    def get_canonical_path(self):
        return Path('/ui')
