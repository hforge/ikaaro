# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from string import Template

# Import from itools
from itools import get_abspath
from itools.datatypes import URI
from itools.gettext import MSG
from itools.handlers import File, Folder, Database
from itools.http import NotFound, Forbidden
from itools.i18n import has_language, get_language_name
from itools.stl import stl
from itools.uri import decode_query
from itools.web import get_context, BaseView
from itools.xml import XMLParser, XMLFile

# Import from ikaaro
from base import Node, DBObject
from folder import Folder as DBFolder
from utils import reduce_string
from widgets import build_menu



class FileGET(BaseView):

    access = True


    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        response = context.response
        response.set_header('Content-Type', resource.get_mimetype())
        return resource.to_str()



class UIFile(Node, File):

    def clone(self, cls=None, exclude=('database', 'uri', 'timestamp',
                                       'dirty', 'parent', 'name')):
        return File.clone(self, cls=cls, exclude=exclude)


    download = FileGET()

    def get_view(self, name, **kw):
        if name is None:
            return self.download
        raise NotFound



class UITemplate(UIFile, XMLFile):
    pass



map = {
    'application/xml': UITemplate,
    'application/xhtml+xml': UITemplate,
    'text/xml': UITemplate,
}



class UIFolder(Node, Folder):

    class_title = MSG(u'UI')
    class_icon48 = 'icons/48x48/folder.png'


    def _get_names(self):
        # FIXME May not be the right implementation
        return self.get_handler_names()


    def _get_object(self, name):
        if self.has_handler(name):
            handler = self.get_handler(name)
        else:
            n = len(name)
            names = [ x for x in self.get_handler_names() if x[:n] == name ]
            languages = [ x.split('.')[-1] for x in names ]
            languages = [ x for x in languages if has_language(x) ]

            if not languages:
                raise LookupError, 'XXX'

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


    #######################################################################
    # Left Menu
    #######################################################################
    def get_main_menu_options(self, context):
        return [
            {'title': MSG(u'Control Panel'),
             'path': '.', 'method': 'control_panel',
             'icon': '/ui/icons/16x16/settings.png'}]


    def get_main_menu(self, context):
        user = context.user
        root = context.site_root
        here = context.resource or root

        menu = []
        for option in self.get_main_menu_options(context):
            object = root.get_object(option['path'])
            # Get the view
            method = option['method']
            view = object.get_view(method)
            # Test security
            ac = object.get_access_control()
            if ac.is_access_allowed(user, object, view):
                menu.append({
                    'href': '%s/;%s' % (here.get_pathto(object), method),
                    'title': option['title'],
                    'class': '',
                    'src': option['icon'],
                    'items': []})

        if not menu:
            return None

        return {'title': MSG(u'Main Menu'),
                'content': build_menu(menu)}


    def get_context_menu(self, context):
        here = context.resource
        if not isinstance(here, DBObject):
            return None

        base = here.get_context_menu_base()
        prefix = context.site_root.get_pathto(base)
        prefix = '/' + str(prefix)

        # Build the menu
        menu = []
        for name, view in base.get_views():
            # Find out the title
            if '?' in name:
                args = name.split('?')[1]
                args = decode_query(args)
            else:
                args = {}
            # Append to the menu
            menu.append({'href': '%s/;%s' % (prefix, name),
                         'title': view.tab_label,
                         'class': '',
                         'src': base.get_method_icon(view, **args),
                         'items': []})

        if not menu:
            return None

        return {'title': base.class_title,
                'content': build_menu(menu)}


    def get_content_language_menu(self, context):
        site_root = context.resource.get_site_root()
        languages = site_root.get_property('website_languages')
        content_language = context.get_cookie('language')
        if content_language is None:
            content_language = languages[0]

        options = []
        for language in languages:
            title = get_language_name(language)
            if language == content_language:
                css_class = 'nav_active'
            else:
                css_class = ''
            options.append({
                'href': context.uri.replace(language=language),
                'src': None,
                'title': title,
                'class': css_class,
                'items': [],
            })

        return {
            'title': MSG(u'Content Language'),
            'content': build_menu(options),
        }


    def get_left_menus(self, context):
        user = context.user

        menus = []
        # Main Menu
        menu = self.get_main_menu(context)
        if menu is not None:
            menus.append(menu)
        # Parent's Menu
        menu = self.get_context_menu(context)
        if menu is not None:
            menus.append(menu)
        # Content language
        if user is not None:
            menu = self.get_content_language_menu(context)
            menus.append(menu)

        return menus


    #######################################################################
    # Breadcrumb
    #######################################################################
    def get_breadcrumb(self, context):
        """Return a list of dicts [{name, url}...]
        """
        root = context.site_root

        # Initialize the breadcrumb with the root resource
        path = '/'
        title = root.get_title()
        breadcrumb = [{
            'url': path,
            'name': title,
            'short_name': reduce_string(title, 15, 30),
            }]

        # Complete the breadcrumb
        resource = root
        for name in context.uri.path:
            path = path + ('%s/' % name)
            try:
                resource = resource.get_object(name)
            except LookupError:
                break
            # Append
            title = resource.get_title()
            breadcrumb.append({
                'url': path,
                'name': title,
                'short_name': reduce_string(title, 15, 30),
            })

        return breadcrumb


    #######################################################################
    # Tabs
    #######################################################################
    def get_tabs(self, context):
        """Return tabs and subtabs as a dict {tabs, subtabs} of list of dicts
        [{name, label, active, style}...].
        """
        def resolve(context, view_name):
            # Case 1: /a/b/;view
            if context.view_name is not None:
                return ';%s' % view_name
            # Case 2: /
            if not context.uri.path:
                return ';%s' % view_name
            # Case 3: /a/b/
            if context.uri.path.endswith_slash:
                return ';%s' % view_name
            # Case 4: /a/b
            return '%s/;%s' % (context.uri.path[-1], view_name)

        # Get request, path, etc...
        here = context.resource
        if here is None:
            return []

        # Get access control
        user = context.user
        ac = here.get_access_control()

        # Tabs
        tabs = []
        for link, view in here.get_views():
            active = False

            # From method?param1=value1&param2=value2&...
            # we separate method and arguments, then we get a dict with
            # the arguments and the subview active state
            if '?' in link:
                name, args = link.split('?')
                args = decode_query(args)
            else:
                name, args = link, {}

            # Active
            if context.view == here.get_view(name, **args):
                active = True

            # Add the menu
            tabs.append({
                'id': 'tab_%s' % name,
                'name': resolve(context, link),
                'label': view.tab_label,
                'active': active,
                'class': active and 'active' or None})

        return tabs


    #######################################################################
    # Objects metadata (context.resource)
    #######################################################################
    def get_metadata_ns(self, context):
        here = context.resource
        if here is None:
            return {'title': '', 'format': '', 'mtime': '', 'icon': ''}
        return {'title': here.get_title(),
                'format': here.class_title,
                'mtime': here.get_mtime().strftime('%Y-%m-%d %H:%M'),
                'icon': here.get_object_icon(size=48)}


    #######################################################################
    # Users info (context.user)
    #######################################################################
    def get_user_menu(self, context):
        """Return a dict {user_icon, user, joinisopen}.
        """
        user = context.user

        if user is None:
            root = context.site_root
            joinisopen = root.get_property('website_is_open')
            return {'info': None, 'joinisopen': joinisopen}

        home = '/users/%s' % user.name
        info = {'name': user.name, 'title': user.get_title(),
                'home': home}
        return {'info': info, 'joinisopen': False}


    #######################################################################
    # Users info (context.user)
    #######################################################################
    def get_message(self, context):
        """Return a message string from de request.
        """
        # FIXME At some point we should deprecate usage of message in the URL
        if context.message is None:
            if context.has_form_value('message'):
                message = context.get_form_value('message')
                return XMLParser(message)

        return context.message


    #######################################################################
    # Styles and Scripts
    #######################################################################
    def get_styles(self, context):
        styles = []
        # Calendar JavaScript Widget (http://dynarch.com/mishoo/calendar.epl)
        styles.append('/ui/calendar/calendar-aruni.css')
        # Aruni (default skin)
        styles.append('/ui/aruni/aruni.css')
        # Calendar
        styles.append('/ui/ical/calendar.css')
        # Table
        styles.append('/ui/table/style.css')
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
        scripts.append('/ui/browser.js')
        scripts.append('/ui/main.js')
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


    #######################################################################
    #
    #######################################################################
    def get_template_title(self, context):
        """Return the title to give to the template document.
        """
        here = context.resource
        # Not Found
        if here is None:
            return u'404 Not Found'
        # In the Root
        root = here.get_site_root()
        if root is here:
            return root.get_title()
        # Somewhere else
        message = MSG(u"${root_title}: ${here_title}")
        return message.gettext(root_title=root.get_title(),
                               here_title=here.get_title())


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


    def build_namespace(self, context):
        namespace = {}
        # CSS & JavaScript
        namespace['styles'] = self.get_styles(context)
        namespace['scripts'] = self.get_scripts(context)
        # Title & Meta
        namespace['title'] = self.get_template_title(context)
        namespace['meta_tags']= self.get_meta_tags(context)
        # User menu
        namespace['user']= self.get_user_menu(context)
        # Left menus
        namespace['left_menus'] = self.get_left_menus(context)
        # Object's metadata & Breadcrumb
        namespace['metadata'] = self.get_metadata_ns(context)
        namespace['breadcrumb'] = self.get_breadcrumb(context)
        # Tabs & Message
        namespace['tabs'] = self.get_tabs(context)
        namespace['message'] = self.get_message(context)
        # View's title (FIXME)
        here = context.resource
        view = context.view
        title = getattr(view, 'page_title', None)
        if callable(title):
            title = title()
        namespace['view_title'] = title
        # Layout
        if context.user is None:
            namespace['layout_class'] = 'layout_not_auth'
        else:
            namespace['layout_class'] = 'layout_auth'

        return namespace


    def get_template(self):
        try:
            return self.get_object('template.xhtml')
        except LookupError:
            # Default, aruni
            return self.get_object('/ui/aruni/template.xhtml')


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

    def _get_object(self, name):
        if name in skin_registry:
            skin = skin_registry[name]
            skin.database = self.database
            return skin
        return UIFolder._get_object(self, name)


