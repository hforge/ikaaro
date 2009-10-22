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

# Import from operator
from operator import itemgetter

# Import from itools
from itools.datatypes import Boolean, Enumerate, String, Unicode
from itools.gettext import MSG
from itools.http import get_context
from itools.i18n import get_language_name, get_languages
from itools.uri import Path
from itools.web import STLView, STLForm, INFO, ERROR
from itools.xapian import PhraseQuery

# Import from ikaaro
from access import RoleAware_BrowseUsers, RoleAware_AddUser
from access import RoleAware_EditMembership
from folder_views import Folder_Orphans
from forms import TextWidget
from forms import SelectField, TextField, Textarea
import messages
from resource_views import DBResource_Edit
from views import IconsView, ContextMenu



###########################################################################
# The menu
###########################################################################
class ControlPanelMenu(ContextMenu):

    title = MSG(u'Control Panel')

    def get_items(self):
        resource = self.resource

        items = []
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(self.context, resource, view):
                continue
            items.append({
                'title': view.title,
                'src': resource.get_method_icon(view, size='16x16'),
                'href': ';%s' % name})

        return items


context_menus = [ControlPanelMenu()]


###########################################################################
# Views
###########################################################################
class ControlPanel(IconsView):

    access = 'is_allowed_to_edit'
    title = MSG(u'Control Panel')
    icon = 'settings.png'
    context_menus = context_menus


    def get_namespace(self, resource, context):
        items = []
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(context, resource, view):
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
    template = 'website/virtual_hosts.xml'
    context_menus = context_menus
    schema = {
        'vhosts': String}


    def get_namespace(self, resource, context):
        vhosts = resource.get_value('vhosts')
        return {
            'vhosts': '\n'.join(vhosts)}


    def action(self, resource, context, form):
        vhosts = [ x.strip() for x in form['vhosts'].splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        resource.set_property('vhosts', vhosts)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED
        context.redirect()



class CPEditSecurityPolicy(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Security Policy')
    icon = 'lock.png'
    description = MSG(u'Choose the security policy.')
    template = 'website/security_policy.xml'
    context_menus = context_menus
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
        context.redirect()



class ContactsOptions(Enumerate):

    def get_options(cls):
        options = []
        resource = cls.resource
        for username in resource.get_users():
            user = get_context().get_user_by_name(username)
            title = user.get_title()
            email = user.get_value('email')
            if title != email:
                user_title = '%s <%s>' % (title, email)
            else:
                user_title = email
            options.append({'name': username, 'value': user_title})
        options.sort(key=itemgetter('value'))
        return options



class CPEditContactOptions(DBResource_Edit):

    access = 'is_allowed_to_edit'
    title = MSG(u'Email options')
    icon = 'mail.png'
    description = MSG(u'Configure the website email options')
    context_menus = context_menus


    emails_signature = TextField(title=MSG(u'Emails signature'))
    emails_signature.widget = Textarea


    def get_field(self, name, resource, context):
        if name == 'emails_from_addr':
            datatype = ContactsOptions(resource=resource)
            title = MSG(u'Emails from addr')
            return SelectField(name, datatype=datatype, title=title)
        elif name == 'contacts':
            datatype = ContactsOptions(multiple=True, resource=resource)
            title = MSG(u'Select the contact accounts')
            return SelectField(name, datatype=datatype, title=title)
        else:
            return DBResource_Edit.get_field(self, name, resource, context)


    field_names = ['emails_from_addr', 'emails_signature', 'contacts']



    def get_value(self, resource, context, name, datatype):
        if name == 'contacts':
            return list(resource.get_value('contacts'))
        return DBResource_Edit.get_value(self, resource, context, name,
                  datatype)


    def action(self, resource, context, form):
        resource.set_property('emails_from_addr', form['emails_from_addr'])
        resource.set_property('emails_signature', form['emails_signature'])
        resource.set_property('contacts', tuple(form['contacts']))
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CPBrokenLinks(STLView):

    access = 'is_admin'
    title = MSG(u'Broken Links')
    icon = 'clear.png'
    description = MSG(u'Check the referential integrity.')
    template = '/ui/website/broken_links.xml'
    context_menus = context_menus


    def get_namespace(self, resource, context):
        # These are all the physical links we have in the database
        links = context.database.catalog.get_unique_values('links')

        # Make a partial search within the website
        root = str(resource.path)
        results = context.get_root_search(root)

        # Find out the broken links within scope and classify them by the
        # origin paths
        broken = {}
        for link in links:
            # Filter links out of scope and not broken links
            link_logical = context.get_logical_path(link)
            if link_logical is None:
                continue
            if context.get_resource(link_logical, soft=True):
                continue
            # Keep in the mapping
            link_logical = str(link_logical)
            for brain in results.search(links=link).get_documents():
                broken.setdefault(brain.abspath, []).append(link_logical)

        # Build the namespace
        items = []
        total = 0
        for path, links in sorted(broken.iteritems()):
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
    template = 'website/edit_languages.xml'
    context_menus = context_menus
    schema = {
        'codes': String(multiple=True, mandatory=True)}


    def get_namespace(self, resource, context):
        ws_languages = resource.get_value('website_languages')

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
        languages = resource.get_value('website_languages')
        languages = [ x for x in languages if x != default ]
        languages.insert(0, default)
        resource.set_property('website_languages', tuple(languages))
        # Ok
        context.message = INFO(u'The default language has been changed.')


    def action_remove_languages(self, resource, context, form):
        codes = form['codes']

        # Check the default language is not to be removed
        languages = resource.get_value('website_languages')
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

        ws_languages = resource.get_value('website_languages')
        resource.set_property('website_languages', ws_languages + (code,))
        # Ok
        context.message = INFO(u'Language added.')
        context.redirect()


class CPEditSEO(DBResource_Edit):

    access = 'is_allowed_to_edit'
    title = MSG(u'Search engine optimization')
    icon = 'search.png'
    description = MSG(u"""
      Optimize your website for better ranking in search engine results.""")
    context_menus = context_menus


    schema = {'google-site-verification': String,
              'yahoo_site_verification': String,
              'bing_site_verification': String}

    widgets = [
        TextWidget('google-site-verification',
            title=MSG(u'Google site verification key')),
        TextWidget('yahoo_site_verification',
            title=MSG(u'Yahoo site verification key')),
        TextWidget('bing_site_verification',
            title=MSG(u'Bing site verification key')),
        ]


    def action(self, resource, context, form):
        for key in self.schema:
            resource.set_property(key, form[key])
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



###########################################################################
# Add the control panel menu to views defined somewhere else
###########################################################################
class CPBrowseUsers(RoleAware_BrowseUsers):
    context_menus = context_menus


class CPAddUser(RoleAware_AddUser):
    context_menus = context_menus


class CPEditMembership(RoleAware_EditMembership):
    context_menus = context_menus


class CPOrphans(Folder_Orphans):
    context_menus = context_menus

