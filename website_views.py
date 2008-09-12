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
import itools
from itools import get_abspath
from itools.datatypes import Boolean, Email, String, Unicode
from itools.datatypes import DynamicEnumerate
from itools.gettext import MSG
from itools.handlers import checkid, merge_dics
from itools.i18n import get_language_name, get_languages
from itools.stl import stl
from itools.uri import Path
from itools import vfs
from itools.web import STLView, STLForm
from itools.xapian import EqQuery, OrQuery, AndQuery, TextField

# Import from ikaaro
import ikaaro
from forms import AutoForm, Select, MultilineWidget, TextWidget
from messages import *
from registry import get_resource_class
from registry import get_register_websites, get_website_class
from resource_views import AddResourceMenu
from views import IconsView, NewInstanceForm, SearchForm, ContextMenu



class NewWebSiteForm(NewInstanceForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Web Site')
    template = '/ui/website/new_instance.xml'
    schema = {
        'name': String,
        'title': Unicode,
    }
    context_menus = [AddResourceMenu()]


    def get_namespace(self, resource, context):
        type = context.get_query_value('type')
        cls = get_resource_class(type)

        websites = []
        for handler_class in get_register_websites():
            title = handler_class.class_title
            websites.append({
                'title': title.gettext(),
                'class_id': handler_class.class_id,
                'selected': False,
                'icon': '/ui/' + handler_class.class_icon16})

        if len(websites) == 1:
            alone = websites[0]
        else:
            alone = None
            websites[0]['selected'] = True

        return {
            'class_title': cls.class_title.gettext(),
            'websites': websites,
            'alone': alone,
        }


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']

        # Check the name
        name = name.strip() or title.strip()
        if not name:
            context.message = MSG_NAME_MISSING
            return

        name = checkid(name)
        if name is None:
            context.message = MSG_BAD_NAME
            return

        # Check the name is free
        if resource.has_resource(name):
            context.message = MSG_NAME_CLASH
            return

        class_id = context.get_form_value('class_id')
        if class_id is None:
            context.message = MSG(u'Please select a website.')
            return

        cls = get_website_class(class_id)
        object = cls.make_resource(cls, resource, name)
        # The metadata
        metadata = object.metadata
        language = resource.get_site_root().get_default_language()
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



###########################################################################
# Views / Forgotten Password
###########################################################################

class ForgottenPasswordForm(STLForm):

    access = True
    title = MSG(u'Forgotten password')
    template = '/ui/website/forgotten_password_form.xml'
    schema = {
        'username': String(default=''),
    }


    def action(self, resource, context, form):
        username = form['username']
        # TODO Don't generate the password, send instead a link to a form
        # where the user will be able to type his new password.
        root = context.root

        # Get the email address
        username = username.strip()

        # Get the user with the given login name
        results = root.search(username=username)
        if results.get_n_documents() == 0:
            goto = ';forgotten_password_form'
            message = MSG(u'There is not a user identified as "$username"')
            context.message =  message.gettext(username=username)
            return

        user = results.get_documents()[0]
        user = resource.get_resource('/users/%s' % user.name)

        # Send email of confirmation
        email = user.get_property('email')
        user.send_confirmation(context, email)

        handler = resource.get_resource('/ui/website/forgotten_password.xml')
        return stl(handler)



###########################################################################
# Views / Control Panel
###########################################################################

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



class VHostsForm(STLForm):

    access = 'is_admin'
    title = MSG(u'Virtual Hosts')
    icon = 'website.png'
    description = MSG(u'Define the domain names for this Web Site.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/virtual_hosts.xml'
    schema = {
        'vhosts': String,
    }


    def get_namespace(self, resource, context):
        vhosts = resource.get_property('vhosts')
        return {
            'vhosts': '\n'.join(vhosts),
        }


    def action(self, resource, context, form):
        vhosts = form['vhosts']
        vhosts = [ x.strip() for x in vhosts.splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        vhosts = tuple(vhosts)
        resource.set_property('vhosts', vhosts)
        # Ok
        context.message = MSG_CHANGES_SAVED



class SecurityPolicyForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Security Policy')
    icon = 'lock.png'
    description = MSG(u'Choose the security policy.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/anonymous.xml'
    schema = {
        'website_is_open': Boolean(default=False),
    }


    def get_namespace(self, resource, context):
        is_open = resource.get_property('website_is_open')
        return {
            'is_open': is_open,
            'is_closed': not is_open,
        }


    def action(self, resource, context, form):
        value = form['website_is_open']
        resource.set_property('website_is_open', value)
        # Ok
        context.message = MSG_CHANGES_SAVED



class ContactOptionsForm(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Contact Options')
    icon = 'mail.png'
    description = MSG(u'Configure the Contact form.')
    context_menus = [ControlPanelMenu()]
    template = '/ui/website/contact_options.xml'
    schema = {
        'contacts': String(multiple=True),
    }


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
        context.message = MSG_CHANGES_SAVED



class BrokenLinks(STLView):

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
        objects = []
        total = 0
        keys = broken.keys()
        keys.sort()
        for path in keys:
            links = broken[path]
            path = str(base.get_pathto(Path(path)))
            n = len(links)
            objects.append({'path': path, 'links': links, 'n': n})
            total += n
        namespace['objects'] = objects
        namespace['total'] = total

        return namespace




class EditLanguagesForm(STLForm):

    access = 'is_admin'
    title = MSG(u'Languages')
    description = MSG(u'Define the Web Site languages.')
    context_menus = [ControlPanelMenu()]
    icon = 'languages.png'
    template = '/ui/website/edit_languages.xml'
    schema = {
        'codes': String(multiple=True, mandatory=True),
    }


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
            'not_active_languages': not_active,
        }


    #######################################################################
    # Actions / Edit
    def action_change_default_language(self, resource, context, form):
        codes = form['codes']

        # This action requires only one language to be selected
        if len(codes) != 1:
            context.message = MSG(
                u'You must select one and only one language.')
            return
        default = codes[0]

        # Change the default language
        languages = resource.get_property('website_languages')
        languages = [ x for x in languages if x != default ]
        languages.insert(0, default)
        resource.set_property('website_languages', tuple(languages))
        # Ok
        context.message = MSG(u'The default language has been changed.')


    def action_remove_languages(self, resource, context, form):
        codes = form['codes']

        # Check the default language is not to be removed
        languages = resource.get_property('website_languages')
        default = languages[0]
        if default in codes:
            context.message = MSG(u'You can not remove the default language.')
            return

        # Remove the languages
        languages = [ x for x in languages if x not in codes ]
        resource.set_property('website_languages', tuple(languages))
        # Ok
        context.message = MSG(u'Languages removed.')


    #######################################################################
    # Actions / Add
    action_add_language_schema = {
        'code': String(mandatory=True)
    }

    def action_add_language(self, resource, context, form):
        code = form['code']

        ws_languages = resource.get_property('website_languages')
        resource.set_property('website_languages', ws_languages + (code,))
        # Ok
        context.message = MSG(u'Language added.')



###########################################################################
# Views / Public
###########################################################################
class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Register')
    submit_value = MSG(u'Register')
    submit_class = 'button_ok'

    schema = {
        'firstname': Unicode(mandatory=True),
        'lastname': Unicode(mandatory=True),
        'email': Email(mandatory=True)}

    widgets = [
        TextWidget('firstname', title=u'First Name'),
        TextWidget('lastname', title=u'Last Name'),
        TextWidget('email', title=u'Email Address')]


    def action(self, resource, context, form):
        # Get input data
        firstname = form['firstname'].strip()
        lastname = form['lastname'].strip()
        email = form['email'].strip()

        # Do we already have a user with that email?
        root = context.root
        results = root.search(email=email)
        users = resource.get_resource('users')
        if results.get_n_documents():
            user = results.get_documents()[0]
            user = users.get_resource(user.name)
            if not user.has_property('user_must_confirm'):
                context.message = MSG(
                    u'There is already an active user with that email.')
                return
        else:
            # Add the user
            user = users.set_user(email, None)
            user.set_property('firstname', firstname, language='en')
            user.set_property('lastname', lastname, language='en')
            # Set the role
            default_role = resource.__roles__[0]['name']
            resource.set_user_role(user.name, default_role)

        # Send confirmation email
        user.send_confirmation(context, email)

        # Bring the user to the login form
        message = MSG(
            u"An email has been sent to you, to finish the registration "
            u"process follow the instructions detailed in it.")
        return message.gettext().encode('utf-8')



class ContactOptions(DynamicEnumerate):

    def get_options(self):
        resource = self.resource
        users = resource.get_resource('/users')

        return [
            {'name': x, 'value': users.get_resource(x).get_title()}
            for x in resource.get_property('contacts')
        ]



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    submit_class = 'button_ok'
    submit_value = MSG(u'Send')

    def get_schema(self, resource, context):
        return {
            'to': ContactOptions(resource=resource, mandatory=True),
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'body': Unicode(mandatory=True)
        }


    widgets = [
        Select('to', title=MSG(u'Recipient')),
        TextWidget('from', title=MSG(u'Sender email address'), size=40),
        TextWidget('subject', title=MSG(u'Subject'), size=40),
        MultilineWidget('body', title=MSG(u'Body'), rows=8, cols=50),
    ]


    def get_value(self, resource, context, name, datatype):
        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_property('email')
        return datatype.default


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = MSG(u'Message sent.')



class SiteSearchView(SearchForm):

    access = True
    title = MSG(u'Search')
    template = '/ui/website/search.xml'

    search_schema = {
        'site_search_text': Unicode,
    }


    def get_namespace(self, resource, context):
        namespace = SearchForm.get_namespace(self, resource, context)
        namespace['text'] = context.query['site_search_text'].strip()
        return namespace


    def get_query_schema(self):
        schema = merge_dics(SearchForm.get_query_schema(self))
        del schema['sort_by']
        del schema['reverse']
        return schema


    def get_search_namespace(self, resource, context):
        text = context.query['site_search_text']
        return {'text': text}


    search_template = '/ui/website/search_form.xml'
    def get_items(self, resource, context):
        text = context.query['site_search_text'].strip()
        if not text:
            return []

        # The Search Query
        query = [ OrQuery(EqQuery('title', word), EqQuery('text', word))
                  for word, kk in TextField.split(text) ]
        if not query:
            return []

        # Search
        abspath = resource.get_canonical_path()
        q1 = EqQuery('paths', str(abspath))
        query = AndQuery(q1, *query)
        root = context.root
        results = root.search(query=query)
        documents = results.get_documents()

        # Check access rights
        user = context.user
        objects = []
        for document in documents:
            object = root.get_resource(document.abspath)
            ac = object.get_access_control()
            if ac.is_allowed_to_view(user, object):
                objects.append(object)

        return objects


    def sort_and_batch(self, resource, context, items):
        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    table_template = '/ui/website/search_table.xml'
    def get_table_namespace(self, resource, context, items):
        # Build the namespace
        items_ns = [{
            'abspath': str(item.get_abspath()),
            'title': item.get_title(),
            'type': item.class_title.gettext(),
            'size': item.get_human_size(),
            'url': '%s/' % resource.get_pathto(item),
            'icon': item.get_class_icon(),
        } for item in items ]

        return {'objects': items_ns}



class AboutView(STLView):

    access = True
    title = MSG(u'About')
    template = '/ui/root/about.xml'


    def get_namespace(self, resource, context):
        return  {
            'itools_version': itools.__version__,
            'ikaaro_version': ikaaro.__version__,
        }



class CreditsView(STLView):

    access = True
    title = MSG(u'Credits')
    template = '/ui/root/credits.xml'


    def get_namespace(self, resource, context):
        context.styles.append('/ui/credits.css')

        # Build the namespace
        credits = get_abspath('CREDITS')
        lines = vfs.open(credits).readlines()
        names = [ x[3:].strip() for x in lines if x.startswith('N: ') ]

        return {'hackers': names}

