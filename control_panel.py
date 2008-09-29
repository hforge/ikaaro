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

# Import from itools
from itools.datatypes import Boolean, String
from itools.gettext import MSG
from itools.i18n import get_language_name, get_languages
from itools.uri import Path
from itools.web import STLView, STLForm, INFO, ERROR
from itools.xapian import EqQuery, AndQuery

# Import from ikaaro
import messages
from views import IconsView, ContextMenu



class ControlPanelMenu(ContextMenu):

    title = MSG(u'Control Panel')

    def get_items(self, resource, context):
        items = []
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(context.user, resource, view):
                continue
            items.append({
                'title': view.title,
                'src': resource.get_method_icon(view, size='16x16'),
                'href': ';%s' % name})

        return items



class ControlPanel(IconsView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Control Panel')
    icon = 'settings.png'
    context_menus = [ControlPanelMenu()]


    def get_namespace(self, resource, context):
        items = []
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(context.user, resource, view):
                continue
            items.append({
                'icon': resource.get_method_icon(view, size='48x48'),
                'title': view.title,
                'description': view.description,
                'url': ';%s' % name})

        return {
            'title': MSG(u'Control Panel'),
            'batch': None,
            'items': items}



class CPEditVirtualHosts(STLForm):

    access = 'is_admin'
    title = MSG(u'Virtual Hosts')
    icon = 'website.png'
    description = MSG(u'Define the domain names for this Web Site.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/virtual_hosts.xml'
    schema = {
        'vhosts': String}


    def get_namespace(self, resource, context):
        vhosts = resource.get_property('vhosts')
        return {
            'vhosts': '\n'.join(vhosts)}


    def action(self, resource, context, form):
        vhosts = form['vhosts']
        vhosts = [ x.strip() for x in vhosts.splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        vhosts = tuple(vhosts)
        resource.set_property('vhosts', vhosts)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CPEditSecurityPolicy(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Security Policy')
    icon = 'lock.png'
    description = MSG(u'Choose the security policy.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/security_policy.xml'
    schema = {
        'website_is_open': Boolean(default=False)}


    def get_namespace(self, resource, context):
        is_open = resource.get_property('website_is_open')
        return {
            'is_open': is_open,
            'is_closed': not is_open}


    def action(self, resource, context, form):
        value = form['website_is_open']
        resource.set_property('website_is_open', value)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CPEditContactOptions(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Contact Options')
    icon = 'mail.png'
    description = MSG(u'Configure the Contact form.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/contact_options.xml'
    schema = {
        'contacts': String(multiple=True)}


    def get_namespace(self, resource, context):
        # Find out the contacts
        contacts = resource.get_property('contacts')

        # Build the namespace
        users = resource.get_resource('/users')
        # Only members of the website are showed
        namespace = {}
        namespace['contacts'] = []
        for username in resource.get_members():
            user = users.get_resource(username)
            email = user.get_property('email')
            if not email:
                continue
            namespace['contacts'].append(
                {'name': username,
                 'email': email,
                 'title': user.get_title(),
                 'is_selected': username in contacts})

        # Sort
        namespace['contacts'].sort(key=lambda x: x['email'])

        return namespace


    def action(self, resource, context, form):
        contacts = form['contacts']
        contacts = tuple(contacts)
        resource.set_property('contacts', contacts)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CPBrokenLinks(STLView):

    access = 'is_admin'
    title = MSG(u'Broken Links')
    icon = 'clear.png'
    description = MSG(u'Check the referential integrity.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/broken_links.xml'


    def get_namespace(self, resource, context):
        root = context.root

        # Find out broken links
        broken = {}
        catalog = context.server.catalog
        base = resource.get_abspath()
        base_str = str(base)
        for link in catalog.get_unique_values('links'):
            if root.has_resource(link):
                continue
            query = AndQuery(EqQuery('paths', base_str),
                             EqQuery('links', link))
            link = str(base.get_pathto(Path(link)))
            for brain in catalog.search(query).get_documents():
                broken.setdefault(brain.abspath, []).append(link)
        # Build the namespace
        namespace = {}
        items = []
        total = 0
        keys = broken.keys()
        keys.sort()
        for path in keys:
            links = broken[path]
            path = str(base.get_pathto(Path(path)))
            n = len(links)
            items.append({'path': path, 'links': links, 'n': n})
            total += n
        namespace['items'] = items
        namespace['total'] = total

        return namespace



class CPEditLanguages(STLForm):

    access = 'is_admin'
    title = MSG(u'Languages')
    description = MSG(u'Define the Web Site languages.')
    context_menus = [ControlPanelMenu()]
    icon = 'languages.png'
    template = '/ui/website/edit_languages.xml'
    schema = {
        'codes': String(multiple=True, mandatory=True)}


    def get_namespace(self, resource, context):
        ws_languages = resource.get_property('website_languages')

        # Active languages
        default = ws_languages[0]
        active = []
        for code in ws_languages:
            language_name = get_language_name(code)
            active.append({
                'code': code,
                'name': language_name,
                'isdefault': code == default})

        # Not active languages
        not_active = [
            x for x in get_languages() if x['code'] not in ws_languages ]
        not_active.sort(lambda x, y: cmp(x['name'], y['name']))

        # Ok
        return {
            'active_languages': active,
            'not_active_languages': not_active}


    #######################################################################
    # Actions / Edit
    def action_change_default_language(self, resource, context, form):
        codes = form['codes']

        # This action requires only one language to be selected
        if len(codes) != 1:
            message = ERROR(u'You must select one and only one language.')
            context.message = message
            return
        default = codes[0]

        # Change the default language
        languages = resource.get_property('website_languages')
        languages = [ x for x in languages if x != default ]
        languages.insert(0, default)
        resource.set_property('website_languages', tuple(languages))
        # Ok
        context.message = INFO(u'The default language has been changed.')


    def action_remove_languages(self, resource, context, form):
        codes = form['codes']

        # Check the default language is not to be removed
        languages = resource.get_property('website_languages')
        default = languages[0]
        if default in codes:
            message = ERROR(u'You can not remove the default language.')
            context.message = message
            return

        # Remove the languages
        languages = [ x for x in languages if x not in codes ]
        resource.set_property('website_languages', tuple(languages))
        # Ok
        context.message = INFO(u'Languages removed.')


    #######################################################################
    # Actions / Add
    action_add_language_schema = {
        'code': String(mandatory=True)}

    def action_add_language(self, resource, context, form):
        code = form['code']

        ws_languages = resource.get_property('website_languages')
        resource.set_property('website_languages', ws_languages + (code,))
        # Ok
        context.message = INFO(u'Language added.')

