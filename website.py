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
    tab_sublabel = MSG(u'Web Site')
    page_title = tab_sublabel
    template = '/ui/website/new_instance.xml'
    schema = {
        'name': String,
        'title': Unicode,
    }


    def get_namespace(self, model, context):
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


    def action(self, model, context, form):
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
        if model.has_object(name):
            context.message = MSG_NAME_CLASH
            return

        class_id = context.get_form_value('class_id')
        if class_id is None:
            context.message = u'Please select a website.'
            return

        cls = get_website_class(class_id)
        object = cls.make_object(cls, model, name)
        # The metadata
        metadata = object.metadata
        language = model.get_site_root().get_default_language()
        metadata.set_property('title', title, language=language)

        goto = './%s/;%s' % (name, object.get_firstview())
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)


###########################################################################
# Views / Login, Logout
###########################################################################
class LoginView(STLView):

    access = True
    tab_label = MSG(u'Login')
    page_title = MSG(u'Login')
    template = '/ui/website/login.xml'


    def get_namespace(self, model, context):
        site_root = model.get_site_root()

        return {
            'action': '%s/;login' % model.get_pathto(site_root),
            'username': context.get_form_value('username'),
        }



    def POST(self, model, context, goto=None):
        email = context.get_form_value('username', type=Unicode)
        password = context.get_form_value('password')

        # Don't send back the password
        keep = ['username']

        # Check the email field has been filed
        email = email.strip()
        if not email:
            message = u'Type your email please.'
            return context.come_back(message, keep=keep)

        # Check the user exists
        root = context.root

        # Search the user by username (login name)
        results = root.search(username=email)
        if results.get_n_documents() == 0:
            message = u'The user "$username" does not exist.'
            return context.come_back(message, username=email, keep=keep)

        # Get the user
        brain = results.get_documents()[0]
        user = root.get_object('users/%s' % brain.name)

        # Check the user is active
        if user.get_property('user_must_confirm'):
            message = u'The user "$username" is not active.'
            return context.come_back(message, username=email, keep=keep)

        # Check the password is right
        if not user.authenticate(password):
            message = MSG(u'The password is wrong.')
            return context.come_back(message, keep=keep)

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


    def get_namespace(self, model, context):
        # Log-out
        context.del_cookie('__ac')
        context.user = None

        return {}



class ForgottenPasswordForm(STLForm):

    access = True
    page_title = MSG(u'Forgotten password')
    template = '/ui/website/forgotten_password_form.xml'
    schema = {
        'username': String(default=''),
    }


    def action(self, model, context, form):
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
        user = model.get_object('/users/%s' % user.name)

        # Send email of confirmation
        email = user.get_property('email')
        user.send_confirmation(context, email)

        handler = model.get_object('/ui/website/forgotten_password.xml')
        return stl(handler)



###########################################################################
# Views / Control Panel
###########################################################################
class ControlPanel(IconsView):

    access = 'is_allowed_to_view'
    tab_label = MSG(u'Control Panel')
    tab_sublabel = MSG(u'Control Panel')
    tab_icon = 'settings.png'
    page_title = tab_sublabel


    def get_namespace(self, model, context):
        namespace = {
            'title': MSG(u'Control Panel'),
            'batch': None,
            'items': [],
        }
        for name in model.get_subviews('control_panel'):
            view = model.get_view(name)
            if view is None:
                continue
            if not model.is_access_allowed(context.user, model, view):
                continue
            namespace['items'].append({
                'icon': model.get_method_icon(view, size='48x48'),
                'title': view.title,
                'description': view.description,
                'url': ';%s' % name})

        return namespace



class VHostsForm(STLForm):

    access = 'is_admin'
    tab_label = MSG(u'Control Panel')
    tab_sublabel = MSG(u'Virtual Hosts')
    tab_icon = 'website.png'
    page_title = tab_sublabel
    description = MSG(u'Define the domain names for this Web Site.')
    template = '/ui/website/virtual_hosts.xml'
    schema = {
        'vhosts': String,
    }


    def get_namespace(self, model, context):
        vhosts = model.get_property('vhosts')
        return {
            'vhosts': '\n'.join(vhosts),
        }


    def action(self, model, context, form):
        vhosts = form['vhosts']
        vhosts = [ x.strip() for x in vhosts.splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        vhosts = tuple(vhosts)
        model.set_property('vhosts', vhosts)
        # Ok
        context.message = MSG_CHANGES_SAVED



class SecurityPolicyForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Control Panel')
    tab_sublabel = MSG(u'Security Policy')
    tab_icon = 'lock.png'
    page_title = tab_sublabel
    description = MSG(u'Choose the security policy.')
    template = '/ui/website/anonymous.xml'
    schema = {
        'website_is_open': Boolean(default=False),
    }


    def get_namespace(self, model, context):
        is_open = model.get_property('website_is_open')
        return {
            'is_open': is_open,
            'is_closed': not is_open,
        }


    def action(self, model, context, form):
        value = form['website_is_open']
        model.set_property('website_is_open', value)
        # Ok
        context.message = MSG_CHANGES_SAVED



class ContactOptionsForm(STLForm):

    access = 'is_allowed_to_edit'
    tab_label = MSG(u'Control Panel')
    tab_sublabel = MSG(u'Contact Options')
    tab_icon = 'mail.png'
    page_title = tab_sublabel
    description = MSG(u'Configure the Contact form.')
    template = '/ui/website/contact_options.xml'
    schema = {
        'contacts': String(multiple=True),
    }


    def get_namespace(self, model, context):
        # Find out the contacts
        contacts = model.get_property('contacts')

        # Build the namespace
        users = model.get_object('/users')
        # Only members of the website are showed
        namespace = {}
        namespace['contacts'] = []
        for username in model.get_members():
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


    def action(self, model, context, form):
        contacts = form['contacts']
        contacts = tuple(contacts)
        model.set_property('contacts', contacts)
        # Ok
        context.message = MSG_CHANGES_SAVED



class BrokenLinks(STLView):

    access = 'is_admin'
    tab_label = MSG(u'Control Panel')
    tab_sublabel = MSG(u'Broken Links')
    tab_icon = 'clear.png'
    page_title = tab_sublabel
    description = MSG(u'Check the referential integrity.')
    template = '/ui/website/broken_links.xml'


    def get_namespace(self, model, context):
        root = context.root

        # Find out broken links
        broken = {}
        catalog = context.server.catalog
        base = model.get_abspath()
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


###########################################################################
# Views / Public
###########################################################################
class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    tab_label = MSG(u'Register')


    form_title = MSG(u'Registration')
    form_action = ';register'
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


    def action(self, model, context, form):
        # Get input data
        firstname = form['firstname'].strip()
        lastname = form['lastname'].strip()
        email = form['email'].strip()

        # Do we already have a user with that email?
        root = context.root
        results = root.search(email=email)
        users = model.get_object('users')
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
            default_role = model.__roles__[0]['name']
            model.set_user_role(user.name, default_role)

        # Send confirmation email
        user.send_confirmation(context, email)

        # Bring the user to the login form
        message = MSG(
            u"An email has been sent to you, to finish the registration "
            u"process follow the instructions detailed in it.")
        return message.gettext().encode('utf-8')



class ContactForm(STLForm):

    access = True
    page_title = MSG(u'Contact')
    template = '/ui/website/contact_form.xml'

    schema = {
        'to': String(mandatory=True),
        'from': Email(mandatory=True),
        'subject': Unicode(mandatory=True),
        'body': Unicode(mandatory=True)}


    def get_namespace(self, model, context):
        # Build the namespace
        namespace = context.build_form_namespace(self.schema)

        # To
        users = model.get_object('/users')
        namespace['contacts'] = []
        for name in model.get_property('contacts'):
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


    def action(self, model, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['body'].strip()

        # Find out the "to" address
        contact = model.get_object('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = model.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = u'Message sent.'


class SiteSearchView(STLView):

    access = True
    page_title = MSG(u'Search')
    template = '/ui/website/search.xml'


    def get_namespace(self, model, context):
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
                abspath = model.get_canonical_path()
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
                info['url'] = '%s/;%s' % (model.get_pathto(object),
                                          object.get_firstview())
                info['icon'] = object.get_class_icon()
                ns_objects.append(info)
            namespace['objects'] = ns_objects
        else:
            namespace['text'] = ''

        return namespace



class AboutView(STLView):

    access = True
    page_title = MSG(u'About')
    template = '/ui/root/about.xml'


    def get_namespace(self, model, context):
        return  {
            'itools_version': itools.__version__,
            'ikaaro_version': ikaaro.__version__,
        }



class CreditsView(STLView):

    access = True
    page_title = MSG(u'Credits')
    template = '/ui/root/credits.xml'


    def get_namespace(self, model, context):
        context.styles.append('/ui/credits.css')

        # Build the namespace
        credits = get_abspath(globals(), 'CREDITS')
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
    class_views = [
        ['browse_content', 'preview_content'],
        ['new_resource'],
        ['edit_metadata'],
        ['control_panel',
         'permissions',
         'new_user',
         'edit_virtual_hosts',
         'edit_security_policy',
         'languages_form',
         'edit_contact_options',
         'broken_links',
         'orphans'],
        ['last_changes']]

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


    def is_allowed_to_register(self, user, object):
        return self.get_property('website_is_open')


    #######################################################################
    # UI
    #######################################################################
    def get_subviews(self, name):
        subviews = Folder.get_subviews(self, name)
        if name == 'control_panel':
            return subviews[1:]
        return subviews


    new_instance = NewWebSiteForm()
    # Control Panel
    control_panel = ControlPanel()
    edit_virtual_hosts = VHostsForm()
    edit_security_policy = SecurityPolicyForm()
    edit_contact_options = ContactOptionsForm()


    #######################################################################
    # UI / Control Panel / Languages
    #######################################################################
    languages_form__access__ = 'is_admin'
    languages_form__label__ = u'Control Panel'
    languages_form__sublabel__ = u'Languages'
    languages_form__description__ = u'Define the Web Site languages.'
    languages_form__icon__ = 'languages.png'
    def languages_form(self, context):
        namespace = {}

        # List of active languages
        languages = []
        website_languages = self.get_property('website_languages')
        default_language = website_languages[0]
        for code in website_languages:
            language_name = get_language_name(code)
            languages.append({'code': code,
                              'name': language_name.gettext(),
                              'isdefault': code == default_language})
        namespace['active_languages'] = languages

        # List of non active languages
        languages = []
        for language in get_languages():
            code = language['code']
            if code not in website_languages:
                languages.append({'code': code,
                                  'name': language['name'].gettext()})
        languages.sort(lambda x, y: cmp(x['name'], y['name']))
        namespace['non_active_languages'] = languages

        handler = self.get_object('/ui/website/languages.xml')
        return stl(handler, namespace)


    change_default_language__access__ = 'is_allowed_to_edit'
    def change_default_language(self, context):
        codes = context.get_form_values('codes')
        if len(codes) != 1:
            return context.come_back(
                u'You must select one and only one language.')

        website_languages = self.get_property('website_languages')
        website_languages = [codes[0]] + [ x for x in website_languages
                                           if x != codes[0] ]
        self.set_property('website_languages', tuple(website_languages))

        message = MSG(u'The default language has been changed.')
        return context.come_back(message)


    remove_languages__access__ = 'is_allowed_to_edit'
    def remove_languages(self, context):
        codes = context.get_form_values('codes')
        website_languages = self.get_property('website_languages')
        default_language = website_languages[0]

        if default_language in codes:
            return context.come_back(
                u'You can not remove the default language.')

        website_languages = [ x for x in website_languages if x not in codes ]
        self.set_property('website_languages', tuple(website_languages))

        message = MSG(u'Languages removed.')
        return context.come_back(message)


    add_language__access__ = 'is_allowed_to_edit'
    def add_language(self, context):
        code = context.get_form_value('code')
        if not code:
            message = MSG(u'You must choose a language')
            return context.come_back(message)

        website_languages = self.get_property('website_languages')
        self.set_property('website_languages', website_languages + (code,))

        message = MSG(u'Language added.')
        return context.come_back(message)


    #######################################################################
    # UI / Control Panel / Broken links
    #######################################################################
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
    license = STLView(access=True, page_title=MSG(u'License'),
                      template='/ui/root/license.xml')


###########################################################################
# Register
###########################################################################
register_object_class(WebSite)
register_website(WebSite)
