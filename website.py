# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
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

# Import from the Standard Library
from decimal import Decimal
from types import GeneratorType

# Import from itools
import itools
from itools import get_abspath
from itools.datatypes import Boolean, Email, Integer, String, Tokens, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import get_language_name, get_languages
from itools.stl import stl
from itools.uri import Path, get_reference
from itools import vfs
from itools.web import FormError, STLView, STLForm
from itools.web import MSG_MISSING_OR_INVALID
from itools.xapian import EqQuery, OrQuery, AndQuery, TextField
from itools.xml import XMLParser

# Import from ikaaro
import ikaaro
from access import RoleAware
from folder import Folder
from forms import TextWidget, AutoForm
from messages import *
from registry import get_object_class, register_object_class
from registry import register_website, get_register_websites, get_website_class
from skins import UI, ui_path
from views import IconsView, NewInstanceForm
import widgets
from workflow import WorkflowAware


###########################################################################
# Views / New
###########################################################################
class NewWebSiteForm(NewInstanceForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Web Site')
    template = '/ui/website/new_instance.xml'
    schema = {
        'name': String,
        'title': Unicode,
    }


    def get_namespace(self, resource, context):
        type = context.get_query_value('type')
        cls = get_object_class(type)

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
        if resource.has_object(name):
            context.message = MSG_NAME_CLASH
            return

        class_id = context.get_form_value('class_id')
        if class_id is None:
            context.message = u'Please select a website.'
            return

        cls = get_website_class(class_id)
        object = cls.make_object(cls, resource, name)
        # The metadata
        metadata = object.metadata
        language = resource.get_site_root().get_default_language()
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)


###########################################################################
# Views / Login, Logout
###########################################################################
class LoginView(STLForm):

    access = True
    title = MSG(u'Login')
    template = '/ui/website/login.xml'
    schema = {
        'username': Unicode(mandatory=True),
        'password': String(mandatory=True),
    }


    def get_namespace(self, resource, context):
        site_root = resource.get_site_root()

        return {
            'action': '%s/;login' % resource.get_pathto(site_root),
            'username': context.get_form_value('username'),
        }


    def action(self, resource, context, form, goto=None):
        email = form['username']
        password = form['password']

        # Check the user exists
        root = context.root

        # Search the user by username (login name)
        results = root.search(username=email)
        if results.get_n_documents() == 0:
            message = MSG(u'The user "$username" does not exist.')
            context.message = message.gettext(username=email)
            return

        # Get the user
        brain = results.get_documents()[0]
        user = root.get_object('users/%s' % brain.name)

        # Check the user is active
        if user.get_property('user_must_confirm'):
            message = MSG(u'The user "$username" is not active.')
            context.message = message.gettext(username=email)
            return

        # Check the password is right
        if not user.authenticate(password):
            context.message = MSG(u'The password is wrong.')
            return

        # Set cookie
        user.set_auth_cookie(context, password)

        # Set context
        context.user = user

        # Come back
        referrer = context.request.referrer
        if referrer:
            if not referrer.path:
                return referrer
            params = referrer.path[-1].params
            if not params:
                return referrer
            if params[0] != 'login':
                return referrer

        if goto is not None:
            return get_reference(goto)

        return get_reference('users/%s' % user.name)



class LogoutView(STLView):
    """Logs out of the application.
    """

    access = True
    template = '/ui/website/logout.xml'


    def get_namespace(self, resource, context):
        # Log-out
        context.del_cookie('__ac')
        context.user = None

        return {}



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
        user = resource.get_object('/users/%s' % user.name)

        # Send email of confirmation
        email = user.get_property('email')
        user.send_confirmation(context, email)

        handler = resource.get_object('/ui/website/forgotten_password.xml')
        return stl(handler)



###########################################################################
# Views / Control Panel
###########################################################################
class ControlPanel(IconsView):

    access = 'is_allowed_to_view'
    title = MSG(u'Control Panel')
    icon = 'settings.png'


    def get_namespace(self, resource, context):
        namespace = {
            'title': MSG(u'Control Panel'),
            'batch': None,
            'items': [],
        }
        for name in resource.class_control_panel:
            view = resource.get_view(name)
            if view is None:
                continue
            if not resource.is_access_allowed(context.user, resource, view):
                continue
            namespace['items'].append({
                'icon': resource.get_method_icon(view, size='48x48'),
                'title': view.title,
                'description': view.description,
                'url': ';%s' % name})

        return namespace



class VHostsForm(STLForm):

    access = 'is_admin'
    title = MSG(u'Virtual Hosts')
    icon = 'website.png'
    description = MSG(u'Define the domain names for this Web Site.')
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
    template = '/ui/website/contact_options.xml'
    schema = {
        'contacts': String(multiple=True),
    }


    def get_namespace(self, resource, context):
        # Find out the contacts
        contacts = resource.get_property('contacts')

        # Build the namespace
        users = resource.get_object('/users')
        # Only members of the website are showed
        namespace = {}
        namespace['contacts'] = []
        for username in resource.get_members():
            user = users.get_object(username)
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
    template = '/ui/website/broken_links.xml'


    def get_namespace(self, resource, context):
        root = context.root

        # Find out broken links
        broken = {}
        catalog = context.server.catalog
        base = resource.get_abspath()
        base_str = str(base)
        for link in catalog.get_unique_values('links'):
            if root.has_object(link):
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

    access = 'is_allowed_to_edit'
    template = '/ui/website/languages_edit.xml'
    schema = {
        'codes': String(multiple=True, mandatory=True),
    }


    def get_namespace(self, resource, context):
        # List of active languages
        languages = resource.get_property('website_languages')
        default = languages[0]

        languages = []
        for code in languages:
            language_name = get_language_name(code)
            languages.append({
                'code': code,
                'name': language_name,
                'isdefault': code == default})

        # Ok
        return {
            'languages': languages,
        }


    def change_default_language(self, resource, context, form):
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


    def remove_languages(self, resource, context, form):
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



class AddLanguageForm(STLForm):

    access = 'is_allowed_to_edit'
    template = '/ui/website/languages_add.xml'
    schema = {
        'code': String(mandatory=True),
    }


    def get_namespace(self, resource, context):
        # List of non active languages
        ws_languages = resource.get_property('website_languages')
        languages = [
            x for x in get_languages() if x['code'] not in ws_languages ]

        # Sort by name
        languages.sort(lambda x, y: cmp(x['name'], y['name']))

        # Ok
        return {
            'languages': languages,
        }


    def add_language(self, resource, context, form):
        ws_languages = resource.get_property('website_languages')
        resource.set_property('website_languages', ws_languages + (code,))
        # Ok
        context.message = MSG(u'Language added.')



class LanguagesForm(STLForm):

    access = 'is_admin'
    title = MSG(u'Languages')
    description = MSG(u'Define the Web Site languages.')
    icon = 'languages.png'



###########################################################################
# Views / Public
###########################################################################
class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Register')


    form_title = MSG(u'Registration')
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
        users = resource.get_object('users')
        if results.get_n_documents():
            user = results.get_documents()[0]
            user = users.get_object(user.name)
            if not user.has_property('user_must_confirm'):
                message = u'There is already an active user with that email.'
                context.message = message
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



class ContactForm(STLForm):

    access = True
    title = MSG(u'Contact')
    template = '/ui/website/contact_form.xml'

    schema = {
        'to': String(mandatory=True),
        'from': Email(mandatory=True),
        'subject': Unicode(mandatory=True),
        'body': Unicode(mandatory=True)}


    def get_namespace(self, resource, context):
        # Build the namespace
        namespace = context.build_form_namespace(self.schema)

        # To
        users = resource.get_object('/users')
        namespace['contacts'] = []
        for name in resource.get_property('contacts'):
            user = users.get_object(name)
            title = user.get_title()
            namespace['contacts'].append({'name': name, 'title': title,
                'selected': name == namespace['to']['value']})

        # From
        if namespace['from']['value'] is None:
            user = context.user
            if user is not None:
                namespace['from']['value'] = user.get_property('email')

        return namespace


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['body'].strip()

        # Find out the "to" address
        contact = resource.get_object('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = u'Message sent.'


class SiteSearchView(STLView):

    access = True
    title = MSG(u'Search')
    template = '/ui/website/search.xml'


    def get_namespace(self, resource, context):
        root = context.root

        # Get and check input data
        text = context.get_form_value('site_search_text', type=Unicode)
        start = context.get_form_value('batchstart', type=Integer, default=0)

        namespace = {}
        if text.strip():
            namespace['text'] = text
            # Search
            query = [ OrQuery(EqQuery('title', word), EqQuery('text', word))
                      for word, kk in TextField.split(text) ]
            if query:
                abspath = resource.get_canonical_path()
                q1 = EqQuery('paths', str(abspath))
                query = AndQuery(q1, *query)
                results = root.search(query=query)
                documents = results.get_documents()
            else:
                documents = []

            # Check access rights
            user = context.user
            objects = []
            for document in documents:
                object = root.get_object(document.abspath)
                ac = object.get_access_control()
                if ac.is_allowed_to_view(user, object):
                    objects.append(object)

            # Batch
            size = 10
            total = len(objects)
            namespace['batch'] = widgets.batch(context.uri, start, size, total)

            # Build the namespace
            ns_objects = []
            for object in objects[start:start+size]:
                info = {}
                info['abspath'] = str(object.get_abspath())
                info['title'] = object.get_title()
                info['type'] = object.class_title.gettext()
                info['size'] = object.get_human_size()
                info['url'] = '%s/' % resource.get_pathto(object)
                info['icon'] = object.get_class_icon()
                ns_objects.append(info)
            namespace['objects'] = ns_objects
        else:
            namespace['text'] = ''

        return namespace



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



###########################################################################
# Model
###########################################################################
class WebSite(RoleAware, Folder):

    class_id = 'WebSite'
    class_version = '20071215'
    class_title = MSG(u'Web Site')
    class_description = MSG(u'Create a new Web Site or Work Place.')
    class_icon16 = 'icons/16x16/website.png'
    class_icon48 = 'icons/48x48/website.png'
    class_skin = 'ui/aruni'
    class_views = ['browse_content', 'preview_content', 'new_resource',
                   'edit_metadata', 'control_panel', 'last_changes']
    class_control_panel = ['permissions', 'new_user', 'edit_virtual_hosts',
                           'edit_security_policy', 'edit_languages',
                           'edit_contact_options', 'broken_links', 'orphans'],


    __fixed_handlers__ = ['skin', 'index']


    def _get_object(self, name):
        if name == 'ui':
            ui = UI(ui_path)
            ui.database = self.metadata.database
            return ui
        if name in ('users', 'users.metadata'):
            return self.parent._get_object(name)
        return Folder._get_object(self, name)


    @classmethod
    def get_metadata_schema(cls):
        schema = Folder.get_metadata_schema()
        schema.update(RoleAware.get_metadata_schema())
        schema['vhosts'] = Tokens(default=())
        schema['contacts'] = Tokens(default=())
        schema['website_languages'] = Tokens(default=('en',))
        return schema


    ########################################################################
    # Publish
    ########################################################################
    unauthorized = LoginView()


    ########################################################################
    # API
    ########################################################################
    def get_default_language(self):
        return self.get_property('website_languages')[0]


    def before_traverse(self, context, min=Decimal('0.000001'),
                        zero=Decimal('0.0')):
        # The default language
        accept = context.accept_language
        default = self.get_default_language()
        if accept.get(default, zero) < min:
            accept.set(default, min)
        # The Query
        language = context.get_form_value('language')
        if language is not None:
            context.set_cookie('language', language)
        # Language negotiation
        user = context.user
        if user is None:
            language = context.get_cookie('language')
            if language is not None:
                accept.set(language, 2.0)
        else:
            language = user.get_property('user_language')
            accept.set(language, 2.0)


    def after_traverse(self, context):
        body = context.entity
        if not isinstance(body, (str, list, GeneratorType, XMLParser)):
            return

        # If there is not content type and the body is not None, wrap it in
        # the skin template
        if context.response.has_header('Content-Type'):
            if isinstance(body, (list, GeneratorType, XMLParser)):
                context.entity = stream_to_str_as_html(body)
            return

        if isinstance(body, str):
            body = XMLParser(body)
        context.entity = context.root.get_skin().template(body)


    def is_allowed_to_register(self, user, object):
        return self.get_property('website_is_open')


    #######################################################################
    # UI
    #######################################################################
    new_instance = NewWebSiteForm()
    # Control Panel
    control_panel = ControlPanel()
    edit_virtual_hosts = VHostsForm()
    edit_security_policy = SecurityPolicyForm()
    edit_contact_options = ContactOptionsForm()
    edit_languages = LanguagesForm()
    broken_links = BrokenLinks()


    #######################################################################
    # UI
    #######################################################################
    register = RegisterForm()
    login = LoginView()
    logout = LogoutView()
    forgotten_password = ForgottenPasswordForm()
    site_search = SiteSearchView()
    contact = ContactForm()
    about = AboutView()
    credits = CreditsView()
    license = STLView(access=True, title=MSG(u'License'),
                      template='/ui/root/license.xml')


###########################################################################
# Register
###########################################################################
register_object_class(WebSite)
register_website(WebSite)
