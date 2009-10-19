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
from itools.core import thingy_lazy_property
from itools.gettext import get_domain
from itools.i18n import get_language_name
from itools.uri import decode_query, get_reference

# Import from ikaaro
from utils import CMSTemplate, reduce_string



###########################################################################
# Global language selector
###########################################################################
class LanguagesTemplate(CMSTemplate):

    template = 'aruni/languages.xml'


    @thingy_lazy_property
    def languages(self):
        context = self.context
        # Website languages
        root = context.get_resource('/')
        ws_languages = root.get_value('website_languages')
        if len(ws_languages) == 1:
            return []

        # Select language
        accept = context.accept_language
        current_language = accept.select_language(ws_languages)

        languages = []
        gettext = get_domain('itools').gettext
        uri = get_reference(context.uri)
        for language in ws_languages:
            selected = (language == current_language)
            css_class = 'selected' if selected else None
            value = get_language_name(language)
            languages.append({
                'name': language,
                'value': gettext(value, language),
                'href': uri.replace(language=language),
                'selected': selected,
                'class': css_class})

        return languages


###########################################################################
# Resource location & menu
###########################################################################
class LocationTemplate(CMSTemplate):

    template = 'aruni/location.xml'

    @thingy_lazy_property
    def breadcrumb(self):
        """Return a list of dicts [{name, url}...]
        """
        context = self.context
        root = context.get_resource('/')

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
        for name in context.path:
            path = path + ('%s/' % name)
            resource = resource.get_resource(name, soft=True)
            if resource is None:
                break
            # Append
            title = resource.get_title()
            breadcrumb.append({
                'url': path,
                'name': title,
                'short_name': reduce_string(title, 15, 30)})

        return breadcrumb


    @thingy_lazy_property
    def tabs(self):
        """Return tabs and subtabs as a dict {tabs, subtabs} of list of dicts
        [{name, label, active, style}...].
        """
        # Get resource & access control
        context = self.context
        here = context.resource
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

