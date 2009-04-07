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
from itools.datatypes import Email, String, Unicode
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.handlers import merge_dicts
from itools.stl import stl
from itools import vfs
from itools.web import STLView, INFO, ERROR
from itools.xapian import PhraseQuery, OrQuery, AndQuery, TextField

# Import from ikaaro
import ikaaro
from forms import AutoForm, SelectWidget, MultilineWidget, TextWidget
import messages
from registry import get_resource_class
from registry import get_register_websites, get_website_class
from resource_views import AddResourceMenu
from views import NewInstanceForm, SearchForm
from utils import get_base_path_query



class NewWebSiteForm(NewInstanceForm):

    access = 'is_allowed_to_add'
    title = MSG(u'Web Site')
    template = '/ui/website/new_instance.xml'
    schema = {
        'name': String,
        'title': Unicode,
        'class_id': String}
    context_menus = [AddResourceMenu()]


    def get_namespace(self, resource, context):
        type = context.get_query_value('type')
        cls = get_resource_class(type)

        # Specific Websites
        websites = get_register_websites()
        websites = list(websites)
        if len(websites) == 1:
            websites = None
        else:
            selected = context.get_form_value('class_id')
            websites = [
                {'title': x.class_title.gettext(),
                 'class_id': x.class_id,
                 'selected': x.class_id == selected,
                 'icon': '/ui/' + x.class_icon16}
                for x in websites ]
            if selected is None:
                websites[0]['selected'] = True

        # Ok
        return {
            'class_id': cls.class_id,
            'class_title': cls.class_title.gettext(),
            'websites': websites}


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        return form['name'].strip() or form['title'].strip()


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']
        class_id = form['class_id']

        # Find out the class id
        if class_id is None:
            websites = get_register_websites()
            websites = list(websites)
            class_id = websites[0].class_id

        # Make resource
        cls = get_website_class(class_id)
        child = cls.make_resource(cls, resource, name)

        # Add title
        metadata = child.metadata
        language = resource.get_site_root().get_default_language()
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class ForgottenPasswordForm(AutoForm):

    access = True
    title = MSG(u'Forgotten password')
    submit_value = MSG(u'Ok')

    widgets = [
        TextWidget('username', title=MSG(u'Type your email address')),
        ]

    schema = query_schema = {'username': Email(default='')}


    def get_value(self, resource, context, name, datatype):
        if name == 'username':
            return context.get_query_value('username')
        return AutoForm.get_value(self, resource, context, name, datatype)


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
            message = ERROR(u'There is not a user identified as "$username"',
                      username=username)
            context.message = message
            return

        user = results.get_documents()[0]
        user = resource.get_resource('/users/%s' % user.name)

        # Send email of confirmation
        email = user.get_property('email')
        user.send_forgotten_password(context, email)

        handler = resource.get_resource('/ui/website/forgotten_password.xml')
        return stl(handler)



class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Register')
    submit_value = MSG(u'Register')

    schema = {
        'firstname': Unicode(mandatory=True),
        'lastname': Unicode(mandatory=True),
        'email': Email(mandatory=True)}

    widgets = [
        TextWidget('firstname', title=MSG(u'First Name')),
        TextWidget('lastname', title=MSG(u'Last Name')),
        TextWidget('email', title=MSG(u'E-mail Address'))]


    def action(self, resource, context, form):
        # Get input data
        firstname = form['firstname'].strip()
        lastname = form['lastname'].strip()
        email = form['email'].strip()

        # Do we already have a user with that email?
        root = context.root
        user = root.get_user_from_login(email)
        if user is not None:
            if not user.has_property('user_must_confirm'):
                message = u'There is already an active user with that email.'
                context.message = ERROR(message)
                return
        else:
            # Add the user
            users = resource.get_resource('users')
            user = users.set_user(email, None)
            user.set_property('firstname', firstname)
            user.set_property('lastname', lastname)
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



class ContactOptions(Enumerate):

    @classmethod
    def get_options(cls):
        resource = cls.resource
        users = resource.get_resource('/users')

        return [
            {'name': x, 'value': users.get_resource(x).get_title()}
            for x in resource.get_property('contacts') ]



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    submit_value = MSG(u'Send')
    query_schema = {'to': String,
                    'subject': Unicode,
                    'body': Unicode}

    def get_schema(self, resource, context):
        return {
            'to': ContactOptions(resource=resource, mandatory=True),
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'body': Unicode(mandatory=True),
        }


    widgets = [
        SelectWidget('to', title=MSG(u'Recipient')),
        TextWidget('from', title=MSG(u'Your email address'), size=40),
        TextWidget('subject', title=MSG(u'Message subject'), size=40),
        MultilineWidget('body', title=MSG(u'Message body'), rows=8, cols=50),
    ]


    def get_value(self, resource, context, name, datatype):
        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_property('email')
        else:
            query = context.query
            if name in query:
                return query[name]
        return datatype.get_default()


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
        context.message = INFO(u'Message sent.')



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
        schema = merge_dicts(SearchForm.get_query_schema(self))
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
        query = [ OrQuery(PhraseQuery('title', word),
                  PhraseQuery('text', word))
                    for word, kk in TextField.split(text) ]
        if not query:
            return []

        # Search
        abspath = resource.get_canonical_path()
        q1= get_base_path_query(str(abspath))
        query = AndQuery(q1, *query)
        root = context.root
        results = root.search(query=query)
        documents = results.get_documents()

        # Check access rights
        user = context.user
        items = []
        for document in documents:
            child = root.get_resource(document.abspath)
            ac = child.get_access_control()
            if ac.is_allowed_to_view(user, child):
                items.append(child)

        return items


    def sort_and_batch(self, resource, context, items):
        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    table_template = '/ui/website/search_table.xml'
    def get_table_namespace(self, resource, context, items):
        # Build the namespace
        site_root = resource.get_site_root()
        items_ns = [{
            'abspath': '/%s' % site_root.get_pathto(item),
            'title': item.get_title(),
            'type': item.class_title.gettext(),
            'size': item.get_human_size(),
            'url': '%s/' % resource.get_pathto(item),
            'icon': item.get_class_icon(),
        } for item in items ]

        return {'items': items_ns}



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

