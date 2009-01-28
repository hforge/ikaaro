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
from itools.handlers import merge_dicts
from itools.uri import Path, get_reference
from itools.vfs import FileName
from itools.web import get_context, BaseView, STLForm, INFO, ERROR

# Import from ikaaro
from datatypes import FileDataType
from forms import AutoForm, title_widget, description_widget, subject_widget
from forms import TextWidget
import messages
from registry import get_resource_class
from utils import get_parameters, reduce_string
from views import NewInstanceForm, ContextMenu



class EditLanguageMenu(ContextMenu):

    title = MSG(u'Edit Language')

    def get_items(self, resource, context):
        content_language = resource.get_content_language(context)

        site_root = resource.get_site_root()
        languages = site_root.get_property('website_languages')
        return [
            {'title': get_language_name(x),
             'href': context.uri.replace(content_language=x),
             'class': 'nav_active' if (x == content_language) else None}
            for x in languages ]



class AddResourceMenu(ContextMenu):

    title = MSG(u'Add Resource')

    def get_items(self, resource, context):
        base = '%s/;new_resource' % context.get_link(resource)
        document_types = resource.get_document_types()
        return [
            {'src': '/ui/' + cls.class_icon16,
             'title': cls.class_title.gettext(),
             'href': '%s?type=%s' % (base, quote(cls.class_id))}
            for cls in document_types ]


class DBResource_NewInstance(NewInstanceForm, AutoForm):

    access = 'is_allowed_to_add'
    query_schema = {
        'type': String}
    schema = {
        'name': String,
        'title': Unicode}
    widgets = [
        title_widget,
        TextWidget('name', title=MSG(u'Name'), default='')]
    submit_value = MSG(u'Add')
    context_menus = [AddResourceMenu()]


    def get_title(self, context):
        if self.title is not None:
            return self.title
        type = context.get_query_value('type')
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_resource_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add $class_title')
        return title.gettext(class_title=class_title)


    def get_new_resource_name(self, form):
        # If the name is not explicitly given, use the title
        name = form['name']
        title = form['title'].strip()
        if name is None:
            return title
        return name or title


    def action(self, resource, context, form):
        name = form['name']
        title = form['title']

        # Create the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = cls.make_resource(cls, resource, name)
        # The metadata
        metadata = child.metadata
        language = resource.get_content_language(context)
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class DBResource_Edit(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit')
    icon = 'metadata.png'
    context_menus = [EditLanguageMenu()]

    schema = {
        'title': Unicode,
        'description': Unicode,
        'subject': Unicode}
    widgets = [title_widget, description_widget, subject_widget]


    def get_value(self, resource, context, name, datatype):
        language = resource.get_content_language(context)
        return resource.get_property(name, language=language)


    def action(self, resource, context, form):
        title = form['title']
        description = form['description']
        subject = form['subject']
        language = resource.get_content_language(context)
        resource.set_property('title', title, language=language)
        resource.set_property('description', description, language=language)
        resource.set_property('subject', subject, language=language)
        # Ok
        context.message = messages.MSG_CHANGES_SAVED



###########################################################################
# Interface to add images from the TinyMCE editor
###########################################################################
class Breadcrumb(object):
    """Instances of this class will be used as namespaces for STL templates.
    The built namespace contains the breadcrumb, that is to say, the path from
    the tree root to another tree node, and the content of that node.
    """

    def __init__(self, filter_types=None, root=None, start=None,
            icon_size=16):
        """The 'start' must be a handler, 'filter_type' must be a handler
        class.
        """
        from file import Image
        from folder import Folder
        from resource_ import DBResource

        if filter_types is None:
            filter_types = (DBResource,)

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
            short_title = reduce_string(title, 12, 40)
            quoted_title = short_title.replace("'", "\\'")
            breadcrumb.insert(0, {'name': node.name,
                                  'title': title,
                                  'short_title': short_title,
                                  'quoted_title': quoted_title,
                                  'url': url})
            node = node.parent
        self.path = breadcrumb

        # Content
        items = []
        self.is_submit = False
        user = context.user
        filters = (Folder,) + filter_types
        for resource in target.search_resources(cls=filters):
            ac = resource.get_access_control()
            if not ac.is_allowed_to_view(user, resource):
                continue
            path = here.get_pathto(resource)
            bc_target = str(root.get_pathto(resource))
            url = context.uri.replace(bc_target=bc_target)

            self.is_submit = True
            # Calculate path
            is_image = isinstance(resource, Image)
            if is_image:
                path_to_icon = ";thumb?width=%s&height=%s" % (icon_size,
                                                              icon_size)
            else:
                path_to_icon = resource.get_resource_icon(icon_size)
            if path:
                path_to_resource = Path(str(path) + '/')
                path_to_icon = path_to_resource.resolve(path_to_icon)
            title = resource.get_title()
            short_title = reduce_string(title, 12, 40)
            quoted_title = short_title.replace("'", "\\'")
            items.append({'name': resource.name,
                          'title': title,
                          'short_title': short_title,
                          'quoted_title': quoted_title,
                          'is_folder': isinstance(resource, Folder),
                          'is_image': is_image,
                          'is_selectable': True,
                          'path': path,
                          'url': url,
                          'icon': path_to_icon,
                          'type': type(resource),
                          'item_type': resource.handler.get_mimetype()})

        items.sort(key=itemgetter('is_folder'), reverse=True)
        self.items = items

        # Avoid general template
        response = context.response
        response.set_header('Content-Type', 'text/html; charset=UTF-8')



class DBResource_AddBase(STLForm):
    """Base class for 'DBResource_AddImage' and 'DBResource_AddLink' (used
    by the Web Page editor).
    """

    access = 'is_allowed_to_edit'

    element_to_add = None

    configuration = {}

    schema = {
        'target_path': String(mandatory=True),
        'target_id': String(default=None),
        'mode': String(mandatory=True),
      }

    styles = ['/ui/bo.css',
              '/ui/aruni/style.css']

    base_scripts = ['/ui/jquery.js',
                    '/ui/javascript.js']


    scripts = {'wiki': ['/ui/wiki/javascript.js'],
               'tiny_mce': ['/ui/tiny_mce/javascript.js',
                            '/ui/tiny_mce/tiny_mce_src.js',
                            '/ui/tiny_mce/tiny_mce_popup.js'],
               'input': []}


    action_upload_schema = merge_dicts(schema,
                                       file=FileDataType(mandatory=True))


    additional_javascript = """
          function select_element(type, value, caption) {
            window.opener.$("#%s").val(value);
            window.close();
          }
          """


    def get_filter_types(self):
        from file import File
        return (File,)


    def get_namespace(self, resource, context):
        from file import File
        # Get some informations
        mode = context.get_form_value('mode')
        # For the breadcrumb
        filter_types = self.get_filter_types()
        if isinstance(resource, File):
            start = resource.parent
        else:
            start = resource
        # Construct namespace
        namespace = self.configuration
        namespace.update({
            'additional_javascript': self.get_additional_javascript(context),
            'bc': Breadcrumb(filter_types=filter_types, start=start,
                             icon_size=48),
            'element_to_add': self.element_to_add,
            'target_id': context.get_form_value('target_id'),
            'message': context.message,
            'mode': mode,
            'resource_action': self.get_resource_action(context),
            'styles': self.styles,
            'scripts': self.get_scripts(mode)})
        return namespace


    def get_scripts(self, mode):
        if mode is None:
            return self.base_scripts
        return self.base_scripts + self.scripts[mode]


    def get_additional_javascript(self, context):
        mode = context.get_form_value('mode')
        if mode!='input':
            return ''
        target_id = context.get_form_value('target_id')
        return self.additional_javascript % target_id


    def action_upload(self, resource, context, form):
        filename, mimetype, body = form['file']
        name, type, language = FileName.decode(filename)

        # Check the filename is good
        name = checkid(name)
        if name is None:
            context.message = messages.MSG_BAD_NAME
            return

        # Get the container
        container = context.root.get_resource(form['target_path'])

        # Check the name is free
        if container.has_resource(name):
            context.message = messages.MSG_NAME_CLASH
            return

        # Check it is of the expected type
        filter_types = self.get_filter_types()
        cls = get_resource_class(mimetype)
        is_compatible = False
        for filter_type in filter_types:
            if issubclass(cls, filter_type):
                is_compatible = True
                break
        if is_compatible is False:
            class_ids = ', '.join([x.class_id for x in filter_types])
            context.message = ERROR(u'The given file is none of the types '
                                    u'$class_ids.', class_ids=class_ids)
            return

        # Add the image to the resource
        cls.make_resource(cls, container, name, body, format=mimetype,
                          filename=filename, extension=type)
        # Get resource path
        child = container.get_resource(name)
        path = resource.get_pathto(child)
        # Add an action to the resource
        action = self.get_resource_action(context)
        if action:
            path = path.resolve2('.%s' % action)
        # Return javascript
        mode = form['mode']
        context.scripts.extend(self.get_scripts(mode))
        return self.get_javascript_return(context, path)


    def get_javascript_return(self, context, path):
        return """
            <script type="text/javascript">
                %s
                select_element('%s', '%s', '');
            </script>""" % (self.get_additional_javascript(context),
                            self.element_to_add, path)


    def get_resource_action(self, context):
        return ''



class DBResource_AddImage(DBResource_AddBase):

    element_to_add = 'image'

    template = '/ui/html/addimage.xml'

    configuration = {'show_browse': True,
                     'show_upload': True}


    def get_filter_types(self):
        from file import Image
        return (Image,)


    def get_resource_action(self, context):
        mode = context.get_form_value('mode')
        if mode=='tiny_mce':
            return '/;download'
        return DBResource_AddBase.get_resource_action(self, context)



class DBResource_AddLink(DBResource_AddBase):

    template = '/ui/html/addlink.xml'

    element_to_add = 'link'

    action_add_resource_schema = merge_dicts(DBResource_AddImage.schema,
                                             title=String(mandatory=True))

    configuration = {'show_browse': True,
                     'show_external': True,
                     'show_insert': True,
                     'show_upload': True}


    def action_add_resource(self, resource, context, form):
        mode = form['mode']
        name = checkid(form['title'])
        # Check name validity
        if name is None:
            context.message = MSG(u"Invalid title.")
            return
        # Get the container
        root = context.root
        container = root.get_resource(context.get_form_value('target_path'))
        # Check the name is free
        if container.has_resource(name):
            context.message = messages.MSG_NAME_CLASH
            return
        # Get the type of resource to add
        cls = self.get_page_type(mode)
        # Create the resource
        child = cls.make_resource(cls, container, name)
        path = context.resource.get_pathto(child)
        context.scripts.extend(self.get_scripts(mode))
        return self.get_javascript_return(context, path)


    def get_page_type(self, mode):
        """Return the type of page to add corresponding to the mode
        """
        if mode=='tiny_mce':
            from wiki.page import WikiPage
            return WikiPage
        elif mode=='wiki':
            from ikaaro.html import WebPage
            return WebPage
        else:
            raise ValueError, 'Incorrect mode %s' % mode


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
        user = root.get_user_from_login(email)
        if user is None:
            message = ERROR(u'The user "$username" does not exist.',
                            username=email)
            context.message = message
            return

        # Check the password is right
        if not user.authenticate(password):
            context.message = ERROR(u'The password is wrong.')
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

        return context.come_back(INFO(u"Welcome!"), goto)



class LogoutView(BaseView):
    """Logs out of the application.
    """

    access = True


    def GET(self, resource, context):
        # Log-out
        context.del_cookie('__ac')
        context.user = None

        message = INFO(u'You Are Now Logged out.')
        return context.come_back(message, goto='./')
