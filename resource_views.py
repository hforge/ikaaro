# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Matthieu France <matthieu@itaapy.com>
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

# Import from the Standard Library
from operator import itemgetter
from urllib import quote

# Import from itools
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import Path, get_reference
from itools.vfs import FileName
from itools.web import BaseView, STLForm, get_context

# Import from ikaaro
from datatypes import FileDataType
from messages import *
from registry import get_resource_class
from utils import get_parameters, reduce_string
from views import NewInstanceForm, ContextMenu



class EditLanguageMenu(ContextMenu):

    title = MSG(u'Edit Language')

    def get_items(self, resource, context):
        site_root = resource.get_site_root()
        languages = site_root.get_property('website_languages')
        content_language = context.get_cookie('language')
        if content_language is None:
            content_language = languages[0]

        return [
            {'title': get_language_name(x),
             'href': context.uri.replace(language=x),
             'class': 'nav_active' if (x == content_language) else None}
            for x in languages ]



class AddResourceMenu(ContextMenu):

    title = MSG(u'Add Resource')

    def get_items(self, resource, context):
        document_types = resource.get_document_types()
        return [
            {'src': '/ui/' + cls.class_icon16,
             'title': cls.class_title.gettext(),
             'href': ';new_resource?type=%s' % quote(cls.class_id)}
            for cls in document_types ]


class DBResourceNewInstance(NewInstanceForm):

    access = 'is_allowed_to_add'
    template = '/ui/base/new_instance.xml'
    query_schema = {
        'type': String}
    schema = {
        'name': String,
        'title': Unicode}
    context_menus = [AddResourceMenu()]


    def get_title(self, context):
        type = context.get_query_value('type')
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_resource_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add $class_title')
        return title.gettext(class_title=class_title)


    def get_namespace(self, resource, context):
        type = context.query['type']
        cls = get_resource_class(type)
        return {
            'title': context.get_form_value('title', type=Unicode),
            'name': context.get_form_value('name', default=''),
            'class_id': cls.class_id,
            'class_title': cls.class_title.gettext(),
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

        # Create the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = cls.make_resource(cls, resource, name)
        # The metadata
        metadata = child.metadata
        language = resource.get_content_language(context)
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class DBResourceEdit(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    icon = 'metadata.png'
    context_menus = [EditLanguageMenu()]

    template = '/ui/base/edit.xml'
    schema = {
        'title': Unicode,
        'description': Unicode,
        'subject': Unicode,
    }


    def get_namespace(self, resource, context):
        language = resource.get_content_language(context)
        language_name = get_language_name(language)

        get_property = resource.get_property
        return {
            'language_name': language_name,
            'title': get_property('title', language=language),
            'description': get_property('description', language=language),
            'subject': get_property('subject', language=language),
        }


    def action(self, resource, context, form):
        title = form['title']
        description = form['description']
        subject = form['subject']
        language = resource.get_content_language(context)
        resource.set_property('title', title, language=language)
        resource.set_property('description', description, language=language)
        resource.set_property('subject', subject, language=language)

        context.message = MSG_CHANGES_SAVED



###########################################################################
# Interface to add images from the TinyMCE editor
###########################################################################
class Breadcrumb(object):
    """Instances of this class will be used as namespaces for STL templates.
    The built namespace contains the breadcrumb, that is to say, the path from
    the tree root to another tree node, and the content of that node.
    """

    def __init__(self, filter_type=None, root=None, start=None,
            icon_size=16):
        """The 'start' must be a handler, 'filter_type' must be a handler
        class.
        """
        from file import Image
        from folder import Folder
        from resource_ import DBResource

        if filter_type is None:
            filter_type = DBResource

        context = get_context()
        here = context.resource
        if root is None:
            root = here.get_site_root()
        if start is None:
            start = root

        # Get the query parameters
        parameters = get_parameters('bc', id=None, target=None)
        id = parameters['id']
        # Get the target folder
        target_path = parameters['target']
        if target_path is None:
            if isinstance(start, Folder):
                target = start
            else:
                target = start.parent
        else:
            target = root.get_resource(target_path)
        self.target_path = str(target.get_abspath())

        # Resource to link
        item = context.get_form_value('item', default='')
        if item == '':
            item = '.'
        self.item = item

        # The breadcrumb
        breadcrumb = []
        node = target
        while node is not root.parent:
            url = context.uri.replace(bc_target=str(root.get_pathto(node)))
            title = node.get_title()
            breadcrumb.insert(0, {'name': node.name,
                                  'title': title,
                                  'short_title': reduce_string(title, 12, 40),
                                  'url': url})
            node = node.parent
        self.path = breadcrumb

        # Content
        items = []
        self.is_submit = False
        user = context.user
        filter = (Folder, filter_type)
        for resource in target.search_resources(cls=filter):
            ac = resource.get_access_control()
            if not ac.is_allowed_to_view(user, resource):
                continue
            path = here.get_pathto(resource)
            bc_target = str(root.get_pathto(resource))
            url = context.uri.replace(bc_target=bc_target)

            self.is_submit = True
            # Calculate path
            path_to_icon = resource.get_resource_icon(icon_size)
            if path:
                path_to_resource = Path(str(path) + '/')
                path_to_icon = path_to_resource.resolve(path_to_icon)
            title = resource.get_title()
            items.append({'name': resource.name,
                          'title': title,
                          'short_title': reduce_string(title, 12, 40),
                          'is_folder': isinstance(resource, Folder),
                          'is_image': isinstance(resource, Image),
                          'is_selectable': True,
                          'path': path,
                          'url': url,
                          'icon': path_to_icon,
                          'item_type': resource.handler.get_mimetype()})

        items.sort(key=itemgetter('is_folder'), reverse=True)
        self.items = items

        # Avoid general template
        response = context.response
        response.set_header('Content-Type', 'text/html; charset=UTF-8')



class DBResourceAddImage(STLForm):

    access = 'is_allowed_to_edit'
    template = '/ui/html/addimage.xml'
    schema = {
        'target_path': String(mandatory=True),
        'file': FileDataType(mandatory=True),
        'mode': String(default='html'),
    }


    def get_namespace(self, resource, context):
        from file import File, Image

        # HTML or Wiki
        mode = context.get_form_value('mode', default='html')
        if mode == 'wiki':
            scripts = ['/ui/wiki/javascript.js']
        else:
            scripts = ['/ui/tiny_mce/javascript.js',
                       '/ui/tiny_mce/tiny_mce_src.js',
                       '/ui/tiny_mce/tiny_mce_popup.js']

        # For the breadcrumb
        if isinstance(resource, File):
            start = resource.parent
        else:
            start = resource

        # Construct namespace
        return {
            'bc': Breadcrumb(filter_type=Image, start=start, icon_size=48),
            'message': context.message,
            'mode': mode,
            'scripts': scripts,
            'caption': MSG_CAPTION.gettext().encode('utf_8'),
        }


    def GET(self, resource, context):
        template = resource.get_resource(self.template)
        namespace = self.get_namespace(resource, context)
        prefix = resource.get_pathto(template)
        return stl(template, namespace, prefix=prefix)


    def action(self, resource, context, form):
        """Allow to upload and add an image to epoz
        """
        from file import Image

        # Check the filename is good
        filename, mimetype, body = form['file']
        name = checkid(filename)
        if name is None:
            context.message = MSG_BAD_NAME
            return

        # Check it is an image
        cls = get_resource_class(mimetype)
        if not issubclass(cls, Image):
            context.message = MSG(u'The given file is not an image.')
            return

        # Get the container
        container = context.root.get_resource(form['target_path'])
        # Check the name is free
        name, type, language = FileName.decode(name)
        if container.has_resource(name):
            context.message = MSG_NAME_CLASH
            return

        # Add the image to the resource
        cls.make_resource(cls, container, name, body, type=type)

        # Ok
        caption = MSG_CAPTION.gettext().encode('utf_8')
        if form['mode'] == 'wiki':
            scripts = ['/ui/wiki/javascript.js']
        else:
            scripts = ['/ui/tiny_mce/javascript.js',
                       '/ui/tiny_mce/tiny_mce_src.js',
                       '/ui/tiny_mce/tiny_mce_popup.js']

        child = container.get_resource(name)
        path = resource.get_pathto(child)
        script_template = '<script type="text/javascript" src="%s" />'
        body = ''
        for script in scripts:
            body += script_template % script

        body += """
            <script type="text/javascript">
                select_img('%s', '%s');
            </script>"""
        return body % (path, caption)



class DBResourceAddLink(STLForm):

    access = 'is_allowed_to_edit'
    template = '/ui/html/addlink.xml'
    schema = {
        'target_path': String(mandatory=True),
        'file': FileDataType(mandatory=True),
        'mode': String(default='html'),
    }


    def get_namespace(self, resource, context):
        from file import File

        # HTML or Wiki
        mode = context.get_form_value('mode', default='html')
        if mode == 'wiki':
            scripts = ['/ui/wiki/javascript.js']
            type = 'WikiPage'
        else:
            scripts = ['/ui/tiny_mce/javascript.js',
                       '/ui/tiny_mce/tiny_mce_src.js',
                       '/ui/tiny_mce/tiny_mce_popup.js']
            type = 'application/xhtml+xml'

        # For the breadcrumb
        if isinstance(resource, File):
            start = resource.parent
        else:
            start = resource

        # Construct namespace
        return {
            'mode': mode,
            'bc': Breadcrumb(filter_type=File, start=start, icon_size=48),
            'message': context.message,
            'scripts': scripts,
            'type': type,
            'wiki_mode': (mode == 'wiki'),
        }


    def GET(self, resource, context):
        template = resource.get_resource(self.template)
        namespace = self.get_namespace(resource, context)
        prefix = resource.get_pathto(template)
        return stl(template, namespace, prefix=prefix)


    def add_page(self, resource, context, form):
        """Allow to upload a file and link it to epoz
        """
        # Get the container
        root = context.root
        container = root.get_resource(context.get_form_value('target_path'))
        # Add the file to the resource
        class_id = context.get_form_value('type')
        cls = get_resource_class(class_id)
        uri = cls.new_instance(cls, container, context)

        if ';add_link' not in uri.path:
            mode = context.get_form_value('mode', default='html')
            if mode == 'wiki':
                scripts = ['/ui/wiki/javascript.js']
            else:
                scripts = ['/ui/tiny_mce/javascript.js',
                           '/ui/tiny_mce/tiny_mce_src.js',
                           '/ui/tiny_mce/tiny_mce_popup.js']

            child = container.get_resource(uri.path[0])
            path = context.resource.get_pathto(child)
            script_template = '<script type="text/javascript" src="%s" />'
            body = ''
            for script in scripts:
                body += script_template % script

            body += """
                <script type="text/javascript">
                    select_link('%s');
                </script>"""
            return body % path

        context.message = uri.query['message']
        return



###########################################################################
# Views / Login, Logout
###########################################################################

class LoginView(STLForm):

    access = True
    title = MSG(u'Login')
    template = '/ui/base/login.xml'
    schema = {
        'username': Unicode(mandatory=True),
        'password': String(mandatory=True),
    }


    def get_namespace(self, resource, context):
        return {
            'username': context.get_form_value('username'),
        }


    def action(self, resource, context, form):
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
        user = root.get_resource('users/%s' % brain.name)

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
        goto = None
        referrer = context.request.referrer
        if referrer:
            if not referrer.path:
                goto = referrer
            else:
                params = referrer.path[-1].params
                if not params:
                    goto = referrer
                elif params[0] != 'login':
                    goto = referrer
        if goto is None:
            goto = get_reference('./')

        return context.come_back(MSG("Welcome!"), goto)



class LogoutView(BaseView):
    """Logs out of the application.
    """

    access = True


    def GET(self, resource, context):
        # Log-out
        context.del_cookie('__ac')
        context.user = None

        message = MSG(u'You Are Now Logged out.')
        return context.come_back(message, goto='./')
