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
from itools.uri import decode_query

# Import from ikaaro
from utils import CMSTemplate, reduce_string



###########################################################################
# Global language selector
###########################################################################
class LanguagesTemplate(CMSTemplate):

    template = '/ui/aruni/languages.xml'


    @thingy_lazy_property
    def languages(self):
        context = self.context
        # Website languages
        site_root = context.site_root
        ws_languages = site_root.get_property('website_languages')
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

    template = '/ui/aruni/location.xml'

    @thingy_lazy_property
    def breadcrumb(self):
        """Return a list of dicts [{name, url}...]
        """
        context = self.context
        site_root = context.site_root

        # Initialize the breadcrumb with the root resource
        path = '/'
        title = site_root.get_title()
        if not title:
            title = site_root.class_title.message.encode('utf_8')
        breadcrumb = [{
            'url': path,
            'name': title,
            'short_name': reduce_string(title, 15, 30)}]

        # Complete the breadcrumb
        resource = site_root
        for name in context.uri.path:
            path = path + ('%s/' % name)
            resource = resource.get_resource(name, soft=True)
            if resource is None:
                break
            # Display resource title only if allowed
            if not site_root.is_allowed_to_view(context.user, resource):
                title = name
            else:
                title = resource.get_title()
            # Append
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
        here_link = context.get_link(here)

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
                'name': '%s/;%s' % (here_link, link),
                'label': view.get_title(context),
                'active': active,
                'class': active and 'active' or None})

        return tabs


    @thingy_lazy_property
    def location(self):
        return bool(self.breadcrumb) or bool(self.tabs)
