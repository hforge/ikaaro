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
from itools.core import thingy_property, thingy_lazy_property
from itools.core import OrderedDict
from itools.datatypes import Boolean, Enumerate, String
from itools.gettext import MSG
from itools.i18n import get_language_name, get_languages
from itools.web import STLView, STLForm, INFO, ERROR
from itools.web import boolean_field, choice_field, input_field
from itools.web import multiple_choice_field, textarea_field

# Import from ikaaro
from access import RoleAware_BrowseUsers, RoleAware_AddUser
from access import RoleAware_EditMembership
from folder_views import Folder_Orphans
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
                'title': view.view_title,
                'src': resource.get_method_icon(view, size='16x16'),
                'href': ';%s' % name})

        return items


context_menus = [ControlPanelMenu()]


###########################################################################
# Views
###########################################################################
class ControlPanel(IconsView):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Control Panel')
    icon = 'settings.png'
    context_menus = context_menus

    def items(self):
        resource = self.resource
        context = self.context

        items = []
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(context, resource, view):
                continue
            items.append({
                'icon': resource.get_method_icon(view, size='48x48'),
                'title': view.view_title,
                'description': view.view_description,
                'url': ';%s' % name})

        return items



class CPEditVirtualHosts(STLForm):

    access = 'is_admin'
    view_title = MSG(u'Virtual Hosts')
    view_description = MSG(u'Define the domain names for this Web Site.')
    icon = 'website.png'
    template = 'website/virtual_hosts.xml'
    context_menus = context_menus

    vhosts = textarea_field(datatype=String)


    def get_value(self, name):
        if name == 'vhosts':
            vhosts = self.resource.get_value('vhosts')
            return '\n'.join(vhosts)

        return super(CPEditVirtualHosts, self).get_value(name)


    def action(self, resource, context, form):
        vhosts = [ x.strip() for x in form['vhosts'].splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        resource.set_property('vhosts', vhosts)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED
        context.redirect()



class CPEditSecurityPolicy(STLForm):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Security Policy')
    icon = 'lock.png'
    view_description = MSG(u'Choose the security policy.')
    template = 'website/security_policy.xml'
    context_menus = context_menus

    website_is_open = boolean_field()


    def is_open(self):
        return self.resource.get_value('website_is_open')


    def action(self, resource, context, form):
        value = form['website_is_open']
        resource.set_property('website_is_open', value)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED
        context.redirect()



def values(self):
    values = []
    resource = self.view.resource
    users = resource.get_resource('/users')
    for username in resource.get_users():
        user = users.get_resource(username)
        email = user.get_value('email')
        title = user.get_title()
        title = email if title == email else '%s <%s>' % (title, email)
        values.append((username, {'title': title}))
    values.sort(key=lambda x: x[1]['title'])

    return OrderedDict(values)



class CPEditContactOptions(DBResource_Edit):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Email options')
    icon = 'mail.png'
    view_description = MSG(u'Configure the website email options')
    context_menus = context_menus

    # Fields
    emails_signature = textarea_field(title=MSG(u'Emails signature'))

    emails_from_addr = choice_field(title=MSG(u'Emails from addr'))
    emails_from_addr.values = thingy_lazy_property(values)

    contacts = multiple_choice_field()
    contacts.title = MSG(u'Select the contact accounts')
    contacts.values = thingy_lazy_property(values)

    field_names = ['emails_from_addr', 'emails_signature', 'contacts']


#   def get_value(self, name):
#       if name == 'contacts':
#           return list(self.resource.get_property('value'))

#       return super(CPEditContactOptions, self).get_value(name)


    def action(self, resource, context, form):
        resource.set_property('emails_from_addr', form['emails_from_addr'])
        resource.set_property('emails_signature', form['emails_signature'])
        resource.set_property('contacts', tuple(form['contacts']))
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



class CPBrokenLinks(STLView):

    access = 'is_admin'
    view_title = MSG(u'Broken Links')
    icon = 'clear.png'
    view_description = MSG(u'Check the referential integrity.')
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




class language_field(choice_field):

    @thingy_lazy_property
    def values(self):
        view = self.view
        languages = set(view.languages)
        values = [
            (x['code'], {'title': x['name']})
            for x in get_languages() if x['code'] not in languages ]
        values = sorted(values, key=lambda x: x[1]['title'])
        values.insert(0, ('', {'title': MSG(u'Choose a language')}))
        return OrderedDict(values)



class CPEditLanguages(STLForm):

    access = 'is_admin'
    view_title = MSG(u'Languages')
    view_description = MSG(u'Define the Web Site languages.')
    icon = 'languages.png'
    template = 'website/edit_languages.xml'
    context_menus = context_menus

    codes = multiple_choice_field(required=True)
    code = language_field(required=True)


    @thingy_lazy_property
    def languages(self):
        return self.resource.get_value('website_languages')


    def active_languages(self):
        languages = self.languages
        default = languages[0]

        return [
            {'code': x, 'name': get_language_name(x),
             'isdefault': x == default}
            for x in languages ]


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
    action_add_language_fields = ['code']
    def action_add_language(self):
        code = self.code.value

        # Change
        resource = self.resource
        ws_languages = resource.get_value('website_languages')
        resource.set_property('website_languages', ws_languages + (code,))

        # Ok
        context = self.context
        context.message = INFO(u'Language added.')
        context.redirect()



class CPEditSEO(DBResource_Edit):

    access = 'is_allowed_to_edit'
    view_title = MSG(u'Search engine optimization')
    icon = 'search.png'
    view_description = MSG(u"""
      Optimize your website for better ranking in search engine results.""")
    context_menus = context_menus


    # Fields
    google_site_verification = input_field()
    google_site_verification.title = MSG(u'Google site verification key')
    title = None
    description = None
    subject = None


    def action(self, resource, context, form):
        resource.set_property('google-site-verification',
            form['google-site-verification'])
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

