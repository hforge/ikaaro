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
from itools import get_abspath
from itools.gettext import MSG
from itools.handlers import File, Folder, Image
from itools.http import NotFound
from itools.i18n import has_language
from itools.stl import stl
from itools.web import get_context, BaseView, ERROR
from itools.xml import XMLFile

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

    def clone(self, cls=None, exclude=('database', 'uri', 'timestamp',
                                       'dirty', 'parent', 'name')):
        return File.clone(self, cls=cls, exclude=exclude)


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
            n = len(name)
            names = [ x for x in self.get_handler_names() if x[:n] == name ]
            languages = [ x.split('.')[-1] for x in names ]
            languages = [ x for x in languages if has_language(x) ]

            if not languages:
                raise LookupError, 'resource "%s" not found' % name

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
            handler = self.get_handler('%s.%s' % (name, language))

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
        # In the Root
        root = here.get_site_root()
        if root is here:
            return root.get_title()
        # Somewhere else
        message = MSG(u"${root_title}: ${here_title}")
        return message.gettext(root_title=root.get_title(),
                               here_title=here.get_title())


    def get_styles(self, context):
        styles = [
            # BackOffice style
            '/ui/bo.css',
            # Calendar JS Widget (http://dynarch.com/mishoo/calendar.epl)
            '/ui/calendar/calendar-aruni.css',
            # Calendar
            '/ui/ical/calendar.css',
            # Table
            '/ui/table/style.css']

        # This skin's style
        if self.has_handler('style.css'):
            styles.append('%s/style.css' % self.get_abspath())
        # Dynamic styles
        for style in context.styles:
            styles.append(style)

        return styles


    def get_scripts(self, context):
        scripts = []
        # Aruni (default skin)
        scripts.append('/ui/jquery.js')
        scripts.append('/ui/javascript.js')
        # Calendar (http://dynarch.com/mishoo/calendar.epl)
        scripts.append('/ui/calendar/calendar.js')
        languages = [
            'af', 'al', 'bg', 'br', 'ca', 'da', 'de', 'du', 'el', 'en', 'es',
            'fi', 'fr', 'hr', 'hu', 'it', 'jp', 'ko', 'lt', 'lv', 'nl', 'no',
            'pl', 'pt', 'ro', 'ru', 'si', 'sk', 'sp', 'sv', 'tr', 'zh']
        accept = context.accept_language
        language = accept.select_language(languages)
        scripts.append('/ui/calendar/lang/calendar-%s.js' % language)
        scripts.append('/ui/calendar/calendar-setup.js')
        # Table
        scripts.append('/ui/table/javascript.js')
        # This skin's JavaScript
        if self.has_handler('javascript.js'):
            scripts.append('%s/javascript.js' % self.get_abspath())
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
        value, language = here.get_property_and_language('description')
        if value:
            meta.append({'name': 'description', 'lang': language,
                         'content': value})
        # Set keywords for all languages
        for language in root.get_property('website_languages'):
            value = here.get_property('subject', language)
            if value is None:
                continue
            value = value.strip()
            if value:
                meta.append({'name': 'keywords', 'lang': language,
                             'content': value})
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
        elif 'message' in context.uri.query:
            # TODO Do not use this anymore
            messages = context.get_query_value('message')
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

        return {
            # HTML head
            'language': language,
            'title': self.get_template_title(context),
            'base_uri': str(uri),
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
        }


    def get_template(self):
        try:
            return self.get_resource('template.xhtml')
        except LookupError:
            # Default, aruni
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

