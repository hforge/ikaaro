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

# Import from itools
from itools.core import proto_lazy_property
from itools.gettext import MSG, get_domain
from itools.i18n import get_language_name
from itools.uri import decode_query

# Import from ikaaro
from utils import CMSTemplate, reduce_string


###########################################################################
# Global language selector
###########################################################################
class LanguagesTemplate(CMSTemplate):

    template = '/ui/default/languages.xml'


    @proto_lazy_property
    def languages(self):
        context = self.context
        # Website languages
        ws_languages = context.root.get_value('website_languages')
        if len(ws_languages) == 1:
            return []

        # Select language
        accept = context.accept_language
        current_language = accept.select_language(ws_languages)

        languages = []
        gettext = get_domain('itools').gettext
        for language in ws_languages:
            href = context.uri.replace(language=language)
            selected = (language == current_language)
            css_class = 'selected' if selected else None
            value = get_language_name(language)
            languages.append({
                'name': language,
                'value': gettext(value, language),
                'href': href,
                'selected': selected,
                'class': css_class})

        return languages


###########################################################################
# Resource location & menu
###########################################################################
class LocationTemplate(CMSTemplate):

    template = '/ui/default/location.xml'

    keep_view_and_query = False

    def get_url(self, path):
        if not self.keep_view_and_query:
            return path
        uri = str(self.context.uri)
        view_and_query = ''
        if '/;' in uri:
            view_and_query = ';' + uri.split('/;')[1]
        return path + view_and_query


    @proto_lazy_property
    def breadcrumb(self):
        """Return a list of dicts [{name, url}...]
        """
        context = self.context
        root = context.root

        # Initialize the breadcrumb with the root resource
        path = '/'
        title = root.get_title()
        if not title:
            title = root.class_title.message.encode('utf_8')
        breadcrumb = [{
            'url': self.get_url(path),
            'name': title,
            'short_name': reduce_string(title, 15, 30)}]

        # Complete the breadcrumb
        resource = root
        for name in context.uri.path:
            path = path + ('%s/' % name)
            resource = resource.get_resource(name, soft=True)
            if resource is None:
                break
            # Display resource title only if allowed
            if not root.is_allowed_to_view(context.user, resource):
                title = name
            else:
                title = resource.get_title()
            # Append
            breadcrumb.append({
                'url': self.get_url(path),
                'name': title,
                'short_name': reduce_string(title, 15, 30)})

        return breadcrumb



class Toolbar(CMSTemplate):

    template = '/ui/default/toolbar.xml'


    @proto_lazy_property
    def resource_title(self):
        return self.resource.get_title()


    @proto_lazy_property
    def items(self):
        """Return the available views of a resource.
        """
        context = self.context
        resource = self.resource
        base_path = context.get_link(resource)

        # Case 1: Anonymous
        user = context.user
        if user is None:
            return [{'url': '%s/;login' % base_path,
                     'title': MSG(u'Sign in'),
                     'css_id': 'toolbar-signin',
                     'subitems': None}]

        # Case 2: Authenticated
        items = [
            # User's profile
            {'url': '/users/%s' % user.name,
             'title': user.get_title(),
             'css_id': 'toolbar-profile',
             'subitems': None},
            # Logout
            {'url': '%s/;logout' % base_path,
             'title': MSG(u'Log out'),
             'css_id': 'toolbar-logout',
             'subitems': None}]

        # Add content
        container = resource
        view = container.get_view('new_resource')
        while view is None:
            container = resource.parent
            view = container.get_view('new_resource')

        if context.is_access_allowed(container, view):
            items.append({
                'url': '%s/;new_resource' % context.get_link(container),
                'title': MSG(u'Add content'),
                'css_id': 'toolbar-add-content',
                'subitems': None})

        # Configuration
        config = resource.get_resource('/config')
        if context.root.is_allowed_to_view(user, config):
            items.append({
                'url': '/config',
                'title': MSG(u'Configuration'),
                'css_id': 'toolbar-configuration',
                'subitems': None})

        # Resource specific
        items.append({
            'url': None,
            'title': MSG(u'Actions...'),
            'css_id': None,
            'subitems': []})

        for link, view in resource.get_views():
            # From method?param1=value1&param2=value2&...
            # we separate method and arguments, then we get a dict with
            # the arguments and the subview active state
            if '?' in link:
                name, args = link.split('?')
                args = decode_query(args)
            else:
                name, args = link, {}

            # Active
            unbound_view = context.view.__bases__[0]
            active = (
                unbound_view is resource.get_view(name, args).__bases__[0])

            # Add the menu
            items[-1]['subitems'].append({
                'url': '%s/;%s' % (base_path, link),
                'title': view.get_title(context),
                'css_id': 'active-view' if active else None})

        return items
