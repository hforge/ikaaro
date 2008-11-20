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
from itools.i18n import get_language_name
from itools.stl import STLTemplate
from itools.uri import decode_query

# Import from ikaaro
from utils import reduce_string



class SkinTemplate(STLTemplate):
    template = None

    def __init__(self, context):
        self.context = context


    def get_template(self):
        template = self.template
        if template is None:
            msg = "%s is missing the 'template' variable"
            raise NotImplementedError, msg % repr(self.__class__)
        return self.context.root.get_resource(template)



###########################################################################
# Global language selector
###########################################################################
class LanguagesTemplate(SkinTemplate):

    template = '/ui/aruni/languages.xml'


    def get_namespace(self):
        context = self.context
        # Website languages
        site_root = context.site_root
        ws_languages = site_root.get_property('website_languages')
        if len(ws_languages) == 1:
            return {'languages': []}

        # Select language
        accept = context.accept_language
        current_language = accept.select_language(ws_languages)

        languages = []
        for language in ws_languages:
            href = context.uri.replace(language=language)
            selected = (language == current_language)
            css_class = 'selected' if selected else None
            languages.append({
                'name': language,
                'value': get_language_name(language),
                'href': href,
                'selected': selected,
                'class': css_class})

        return {'languages': languages}


###########################################################################
# Resource location & menu
###########################################################################
class LocationTemplate(SkinTemplate):

    template = '/ui/aruni/location.xml'


    def get_breadcrumb(self, context):
        """Return a list of dicts [{name, url}...]
        """
        site_root = context.site_root

        # Initialize the breadcrumb with the root resource
        path = '/'
        title = site_root.get_title()
        breadcrumb = [{
            'url': path,
            'name': title,
            'short_name': reduce_string(title, 15, 30),
            }]

        # Complete the breadcrumb
        resource = site_root
        for name in context.uri.path:
            path = path + ('%s/' % name)
            try:
                resource = resource.get_resource(name)
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


    def get_tabs(self, context):
        """Return tabs and subtabs as a dict {tabs, subtabs} of list of dicts
        [{name, label, active, style}...].
        """
        # Get request, path, etc...
        here = context.resource

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
            if context.view == here.get_view(name, args):
                active = True

            # Add the menu
            tabs.append({
                'name': ';%s' % link,
                'label': view.get_title(context),
                'active': active,
                'class': active and 'active' or None})

        return tabs


    def get_namespace(self):
        context = self.context
        return {
            'breadcrumb': self.get_breadcrumb(context),
            'tabs': self.get_tabs(context)}
