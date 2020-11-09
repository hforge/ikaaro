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
from itools.web import STLView, INFO, ERROR

# Import from ikaaro

# Import from here
from folder import Folder
from messages import MSG_CHANGES_SAVED
from views import IconsView


###########################################################################
# Views
###########################################################################
GROUPS = [
    ('access', MSG(u'Users, Access Control & Security')),
    ('webmaster', MSG(u'Webmaster tools')),
    ('content', MSG(u'Content')),
    ('other', MSG(u'Other')),
    ]


class Configuration_View(STLView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Configuration')
    template = '/ui/ikaaro/website/config.xml'

    def get_namespace(self, resource, context):
        newmodules = []
        groups = {}

        # Core views (non persistent)
        for name in resource.class_core_views:
            view = resource.get_view(name)
            if view is None:
                continue
            if not context.is_access_allowed(resource, view):
                continue
            group_name = getattr(view, 'config_group', 'other')
            groups.setdefault(group_name, []).append({
                'icon': resource.get_method_icon(view, size='48x48'),
                'title': view.title,
                'description': view.description,
                'url': ';%s' % name})

        # Plugins (persistent)
        for name in resource._modules:
            module = resource.get_resource(name, soft=True)
            if module is None:
                newmodules.append(name)
                continue
            group_name = getattr(module, 'config_group', 'other')
            groups.setdefault(group_name, []).append({
                'icon': module.get_class_icon(48),
                'title': module.class_title,
                'description': module.class_description,
                'url': name})

        groups_ns = [
            {'title': title, 'items': groups[name]}
            for (name, title) in GROUPS if name in groups ]

        # Ok
        return {'newmodules': newmodules, 'groups': groups_ns}


    def action(self, resource, context, form):
        for name, module in resource._modules.items():
            if resource.get_resource(name, soft=True) is None:
                resource.make_resource(name, module)

        context.message = MSG(u'New modules initialized.')



class Config_EditLanguages(STLView):

    access = 'is_admin'
    title = MSG(u'Languages')
    description = MSG(u'Define the Web Site languages.')
    icon = 'languages.png'
    template = '/ui/ikaaro/website/edit_languages.xml'
    schema = {'codes': String(multiple=True, mandatory=True)}

    config_group = 'webmaster'


    def get_namespace(self, resource, context):
        ws_languages = context.root.get_value('website_languages')

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
        resource = context.root

        # This action requires only one language to be selected
        codes = form['codes']
        if len(codes) != 1:
            message = ERROR(u'You must select one and only one language.')
            context.message = message
            return
        default = codes[0]

        # Change the default language
        languages = resource.get_value('website_languages')
        languages = [ x for x in languages if x != default ]
        languages.insert(0, default)
        resource.set_property('website_languages', languages)
        # Ok
        context.message = MSG_CHANGES_SAVED


    def action_remove_languages(self, resource, context, form):
        resource = context.root

        # Check the default language is not to be removed
        codes = form['codes']
        languages = resource.get_value('website_languages')
        default = languages[0]
        if default in codes:
            message = ERROR(u'You can not remove the default language.')
            context.message = message
            return

        # Remove the languages
        languages = [ x for x in languages if x not in codes ]
        resource.set_property('website_languages', languages)
        # Ok
        context.message = INFO(u'Languages removed.')


    #######################################################################
    # Actions / Add
    action_add_language_schema = {
        'code': String(mandatory=True)}

    def action_add_language(self, resource, context, form):
        resource = context.root

        ws_languages = resource.get_value('website_languages')
        ws_languages = list(ws_languages)
        ws_languages.append(form['code'])
        resource.set_property('website_languages', ws_languages)
        # Ok
        context.message = INFO(u'Language added.')



###########################################################################
# Persistent object '/config'
###########################################################################
class Configuration(Folder):

    class_id = 'configuration'
    class_title = MSG(u'Configuration')
    class_views = ['view', 'edit_languages']
    class_icon_css = 'fa-cogs'


    def init_resource(self, **kw):
        super(Configuration, self).init_resource(**kw)
        for name, module in self._modules.items():
            self.make_resource(name, module, soft=True)


    # Plugins
    _modules = {}

    @classmethod
    def register_module(cls, module):
        cls._modules[module.config_name] = module


    @classmethod
    def unregister_module(cls, name):
        del cls._modules[name]


    # Views
    view = IconsView()
    edit_languages = Config_EditLanguages()
