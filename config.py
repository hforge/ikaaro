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
from itools.datatypes import String
from itools.gettext import MSG
from itools.i18n import get_language_name, get_languages
from itools.uri import Path
from itools.web import STLView, STLForm, INFO, ERROR
from itools.database import PhraseQuery

# Import from ikaaro
from access import RoleAware_BrowseUsers, RoleAware_AddUser
from access import RoleAware_EditMembership
from folder import Folder
from messages import MSG_CHANGES_SAVED
from utils import get_base_path_query
from views import IconsView



###########################################################################
# Views
###########################################################################
class Configuration_View(IconsView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Configuration')


    def get_namespace(self, resource, context):
        items = []

        # Core views (non persistent)
        ac = resource.get_access_control()
        for name in resource.class_core_views:
            view = resource.get_view(name)
            if view is None:
                continue
            if not ac.is_access_allowed(context.user, resource, view):
                continue
            items.append({
                'icon': resource.get_method_icon(view, size='48x48'),
                'title': view.title,
                'description': view.description,
                'url': ';%s' % name})

        # Plugins (persistent)
        for name in resource._plugins:
            plugin = resource.get_resource(name, soft=True)
            if plugin is None:
                raise NotImplementedError
            items.append({
                'icon': plugin.get_class_icon(48),
                'title': plugin.class_title,
                'description': plugin.class_description,
                'url': name})

        # Ok
        return {
            'title': MSG(u'Configuration'),
            'batch': None,
            'items': items}



class CPEditVirtualHosts(STLForm):

    access = 'is_admin'
    title = MSG(u'Virtual Hosts')
    icon = 'website.png'
    description = MSG(u'Define the domain names for this Web Site.')
    template = '/ui/website/virtual_hosts.xml'
    schema = {
        'vhosts': String}


    def get_namespace(self, resource, context):
        resource = resource.get_site_root()

        vhosts = resource.get_property('vhosts')
        return {'vhosts': '\n'.join(vhosts)}


    def action(self, resource, context, form):
        resource = resource.get_site_root()

        vhosts = [ x.strip() for x in form['vhosts'].splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        resource.set_property('vhosts', vhosts)
        # Ok
        context.message = MSG_CHANGES_SAVED



class CPBrokenLinks(STLView):

    access = 'is_admin'
    title = MSG(u'Broken Links')
    icon = 'clear.png'
    description = MSG(u'Check the referential integrity.')
    template = '/ui/website/broken_links.xml'


    def get_namespace(self, resource, context):
        # Find out broken links
        catalog = context.database.catalog
        base = resource.get_canonical_path()

        # Search only within the given resource
        query = get_base_path_query(base, include_container=True)
        results = catalog.search(query)

        # Find out the broken links
        root = context.root
        broken = {}
        for link in catalog.get_unique_values('links'):
            if root.get_resource(link, soft=True) is not None:
                continue
            sub_results = results.search(PhraseQuery('links', link))
            link = str(base.get_pathto(Path(link)))
            for brain in sub_results.get_documents():
                broken.setdefault(brain.abspath, []).append(link)

        # Build the namespace
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

        return {
            'items': items,
            'total': total}



class CPEditLanguages(STLForm):

    access = 'is_admin'
    title = MSG(u'Languages')
    description = MSG(u'Define the Web Site languages.')
    icon = 'languages.png'
    template = '/ui/website/edit_languages.xml'
    schema = {
        'codes': String(multiple=True, mandatory=True)}


    def get_namespace(self, resource, context):
        resource = resource.get_site_root()
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
        resource = resource.get_site_root()

        # This action requires only one language to be selected
        codes = form['codes']
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
        context.message = MSG_CHANGES_SAVED


    def action_remove_languages(self, resource, context, form):
        resource = resource.get_site_root()

        # Check the default language is not to be removed
        codes = form['codes']
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
        resource = resource.get_site_root()

        ws_languages = resource.get_property('website_languages')
        ws_languages = list(ws_languages)
        ws_languages.append(form['code'])
        resource.set_property('website_languages', tuple(ws_languages))
        # Ok
        context.message = INFO(u'Language added.')



###########################################################################
# Persistent object '/config'
###########################################################################
class Configuration(Folder):

    class_id = 'configuration'
    class_title = MSG(u'Configuration')
    is_content = False

    class_core_views = ['browse_users', 'add_user', 'edit_virtual_hosts',
                        'edit_languages', 'broken_links', 'orphans']

    
    _plugins = {}

    @classmethod
    def register_plugin(cls, name, plugin):
        cls._plugins[name] = plugin


    def init_resource(self, **kw):
        super(Configuration, self).init_resource(**kw)
        for name, plugin in self._plugins.items():
            self.make_resource(name, plugin)


    view = Configuration_View()

    # Control Panel
    browse_users = RoleAware_BrowseUsers()
    add_user = RoleAware_AddUser()
    edit_membership = RoleAware_EditMembership()
    edit_virtual_hosts = CPEditVirtualHosts()
    edit_languages = CPEditLanguages()
    broken_links = CPBrokenLinks()


# Import core config modules
import config_access
import config_captcha
import config_mail
import config_seo
import config_theme
