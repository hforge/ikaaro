# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2008 Matthieu France <matthieu@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2010 Alexis Huet <alexis@itaapy.com>
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
from itools.core import merge_dicts, proto_property, proto_lazy_property
from itools.csv import Property
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.fs import FileName
from itools.uri import Path
from itools.web import STLView, ERROR

# Import from ikaaro
from buttons import AddButton
from datatypes import FileDataType
from folder_views import Folder_BrowseContent
import messages
from utils import reduce_string, make_stl_template


class SelectElement(AddButton):
    template = make_stl_template('''
        <button type="submit" name="action" value="" id="${css}"
          class="${css}" onclick="${onclick}">${title}</button>''')


    @proto_property
    def onclick(cls):
        element = cls.element_to_add
        return 'select_element("%s", $(this).attr("value"), "")' % element



###########################################################################
# Browse class
###########################################################################
class AddBase_BrowseContent(Folder_BrowseContent):
    access = 'is_allowed_to_edit'
    context_menus = []

    search_schema = {}
    search_widgets =[]

    table_template = '/ui/html/addbase_browse_table.xml'

    folder_classes = ()

    # Parameter for get_items
    target = None
    popup_root = None

    # Table
    table_columns = [
        ('checkbox', None),
        ('icon', None),
        ('name', MSG(u'Name')),
        ('mtime', MSG(u'Last Modified')),
        ('last_author', MSG(u'Last Author'))]

    table_actions = [SelectElement]


    def get_folder_classes(self):
        if self.folder_classes:
            return self.folder_classes
        from folder import Folder
        return (Folder,)


    def is_folder(self, resource):
        bases = self.get_folder_classes()
        return isinstance(resource, bases)


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            # radiobox
            id = str(item.abspath) + self.resource_action
            return id, False
        elif column == 'name':
            target = self.target
            if self.is_folder(item):
                path_to_item = context.root.get_pathto(item)
                url_dic = {'target': str(path_to_item),
                           # Avoid search conservation
                           'search_text': None,
                           'search_type': None,
                           # Reset batch
                           'batch_start': None}
                url = context.uri.replace(**url_dic)
            else:
                url = None
            path = target.abspath.get_pathto(item.abspath)
            return unicode(path), url
        else:
            proxy = super(AddBase_BrowseContent, self)
            return proxy.get_item_value(resource, context, item, column)


    def get_items(self, resource, context):
        proxy = super(AddBase_BrowseContent, self)
        return proxy.get_items(self.target, context)


    @proto_lazy_property
    def actions_namespace(self):
        resource = self.resource
        context = self.context
        items = self._items

        actions = []
        for button in self.get_table_actions(resource, context):
            button = button(resource=resource, context=context,
                            items=items, element_to_add=self.element_to_add)
            if button.show:
                actions.append(button)
        return actions



class AddImage_BrowseContent(AddBase_BrowseContent):

    base_classes = ('folder', 'image')


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            if self.is_folder(item):
                return None
            proxy = super(AddImage_BrowseContent, self)
            return proxy.get_item_value(resource, context, item, column)
        elif column == 'icon':
            if self.is_folder(item):
                # icon
                path_to_icon = item.get_resource_icon(48)
                if path_to_icon.startswith(';'):
                    path_to_icon = Path('%s/' % item.name).resolve(path_to_icon)
            else:
                path = item.abspath
                path_to_icon = ";thumb?width48=&height=48"
                if path:
                    path_to_resource = Path(str(path) + '/')
                    path_to_icon = path_to_resource.resolve(path_to_icon)
            return path_to_icon
        else:
            proxy = super(AddImage_BrowseContent, self)
            return proxy.get_item_value(resource, context, item, column)



class AddMedia_BrowseContent(AddBase_BrowseContent):

    base_classes = ('folder', 'video', 'application/x-shockwave-flash')



###########################################################################
# Interface to add images from the TinyMCE editor
###########################################################################
class DBResource_AddBase(STLView):
    """Base class for 'DBResource_AddImage' and 'DBResource_AddLink' (used
    by the Web Page editor).
    """

    access = 'is_allowed_to_add'
    template = '/ui/html/popup.xml'

    element_to_add = None

    schema = {
        'target_path': String(mandatory=True),
        'target_id': String(default=None),
        'mode': String(default='')}

    search_widgets = []
    search_schema = {}

    # This value must be set in subclass
    browse_content_class = None
    query_schema = merge_dicts(Folder_BrowseContent.query_schema,
                               search_schema, target=String)
    action_upload_schema = merge_dicts(schema, title=Unicode,
                                       file=FileDataType(mandatory=True))


    def get_configuration(self):
        return {}


    def get_root(self, context):
        return context.root


    def get_start(self, resource):
        from file import File
        if isinstance(resource, File):
            return resource.parent
        return resource


    def can_upload(self, cls):
        base_classes = self.browse_content_class.base_classes
        if base_classes is None:
            return True

        for base_class in cls.__mro__:
            if getattr(base_class, 'class_id', None) in base_classes:
                return True

        return False


    def get_namespace(self, resource, context):
        from folder import Folder

        # For the breadcrumb
        start = self.get_start(resource)

        # Get the query parameters
        target_path = context.get_form_value('target')
        # Get the target folder
        popup_root = self.get_root(context)
        popup_root_abspath = popup_root.abspath
        if target_path is None:
            if isinstance(start, Folder):
                target = start
            else:
                target = start.parent
        else:
            target = popup_root.get_resource(target_path)
            if target_path.startswith('/'):
                target_path = target_path.lstrip('/')
            target_path = popup_root_abspath.resolve2(target_path)
            target = resource.get_resource(target_path)
            prefix = popup_root_abspath.get_prefix(target_path)
            # Check popup chroot
            if prefix != popup_root_abspath:
                target = popup_root
        # The breadcrumb
        breadcrumb = []
        node = target
        get_prefix = popup_root_abspath.get_prefix
        while node and get_prefix(node.abspath) == popup_root_abspath:
            path_to_node = popup_root_abspath.get_pathto(node.abspath)
            url_dic = {'target': str(path_to_node),
                       # Avoid search conservation
                       'search_text': None,
                       'search_type': None,}
            url = context.uri.replace(**url_dic)
            title = node.get_title()
            short_title = reduce_string(title, 12, 40)
            quoted_title = short_title.replace("'", "\\'")
            breadcrumb.insert(0, {'name': node.name,
                                  'title': title,
                                  'short_title': short_title,
                                  'quoted_title': quoted_title,
                                  'url': url})
            node = node.parent

        # Avoid general template
        context.content_type = 'text/html; charset=UTF-8'

        # Build and return the namespace
        root = context.root
        namespace = self.get_configuration()
        additional_javascript = self.get_additional_javascript(context)
        namespace['text'] = self.text_values
        namespace['additional_javascript'] = additional_javascript
        namespace['target_path'] = str(target.abspath)
        namespace['breadcrumb'] = breadcrumb
        namespace['element_to_add'] = self.element_to_add
        namespace['target_id'] = context.get_form_value('target_id')
        namespace['message'] = context.message
        namespace['mode'] = context.get_form_value('mode')
        namespace['scripts'] = self.get_scripts(context)
        namespace['styles'] = root.get_skin(context).get_styles(context)
        browse_content = self.browse_content_class(
                           element_to_add=self.element_to_add,
                           resource_action=self.get_resource_action(context),
                           target=target, popup_root=popup_root,
                           # bind
                           resource=resource, context=context)
        namespace['browse_table'] = browse_content.GET(resource, context)
        return namespace


    def get_scripts(self, context):
        mode = context.get_form_value('mode')
        if mode == 'tiny_mce':
            return ['/ui/tiny_mce/javascript.js',
                    '/ui/tiny_mce/tiny_mce_src.js',
                    '/ui/tiny_mce/tiny_mce_popup.js']
        return []


    def get_additional_javascript(self, context):
        mode = context.get_form_value('mode')
        if mode != 'input':
            return ''

        additional_javascript = """
            function select_element(type, value, caption) {
                window.opener.$("#%s").val(value);
                window.close();
            }
            """

        target_id = context.get_form_value('target_id')
        # As ':' is a css selector, escape it
        return additional_javascript % target_id.replace(':', r'\\:')


    def action_upload(self, resource, context, form):
        filename, mimetype, body = form['file']
        name, type, language = FileName.decode(filename)

        # Check the filename is good
        title = form['title'].strip()
        name = checkid(title) or checkid(name)
        if name is None:
            context.message = messages.MSG_BAD_NAME
            return

        # Get the container
        container = context.root.get_resource(form['target_path'])

        # Check the name is free
        if container.get_resource(name, soft=True) is not None:
            context.message = messages.MSG_NAME_CLASH
            return

        # Check it is of the expected type
        cls = context.database.get_resource_class(mimetype)
        if not self.can_upload(cls):
            error = u'The given file is not of the expected type.'
            context.message = ERROR(error)
            return

        kw = {'data': body, 'filename': filename}

        # Add the image to the resource
        child = container.make_resource(name, cls, **kw)
        # The title
        language = resource.get_edit_languages(context)[0]
        title = Property(title, lang=language)
        child.metadata.set_property('title', title)
        # Get the path
        path = child.abspath
        action = self.get_resource_action(context)
        if action:
            path = '%s%s' % (path, action)
        # Return javascript
        scripts = self.get_scripts(context)
        context.add_script(*scripts)
        return self.get_javascript_return(context, path)


    def get_javascript_return(self, context, path):
        return """
            <script type="text/javascript">
              <!--
              %s
              select_element('%s', '%s', '');
              //-->
            </script>""" % (self.get_additional_javascript(context),
                            self.element_to_add, path)


    def get_resource_action(self, context):
        return ''



class DBResource_AddLink(DBResource_AddBase):

    element_to_add = 'link'
    browse_content_class = AddBase_BrowseContent

    action_add_resource_schema = merge_dicts(DBResource_AddBase.schema,
                                             title=Unicode(mandatory=True))

    text_values = {'title': MSG(u'Insert link'),
       'browse': MSG(u'Browse and link to a File from the workspace'),
       'extern': MSG(u'Type the URL of an external resource'),
       'insert': MSG(u'Create a new page and link to it:'),
       'upload': MSG(u'Upload a file to the current folder and link to it:'),
       'method': ';add_link'}


    def get_configuration(self):
        return {
            'show_browse': True,
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
        if container.get_resource(name, soft=True) is not None:
            context.message = messages.MSG_NAME_CLASH
            return
        # Get the type of resource to add
        cls = self.get_page_type(mode)
        # Create the resource
        child = container.make_resource(name, cls)
        scripts = self.get_scripts(context)
        context.add_script(*scripts)
        return self.get_javascript_return(context, child.abspath)


    def get_page_type(self, mode):
        """Return the type of page to add corresponding to the mode
        """
        if mode == 'tiny_mce':
            from webpage import WebPage
            return WebPage
        raise ValueError, 'Incorrect mode %s' % mode



class DBResource_AddImage(DBResource_AddBase):

    element_to_add = 'image'
    browse_content_class = AddImage_BrowseContent

    text_values = {'title': MSG(u'Insert image'),
       'browse': MSG(u'Browse and insert an Image from the workspace'),
       'extern': None,
       'insert': None,
       'upload': MSG(u'Upload an image to the current folder and insert it:'),
       'method': ';add_image'}


    def get_configuration(self):
        return {
            'show_browse': True,
            'show_external': False,
            'show_insert': False,
            'show_upload': True}


    def get_resource_action(self, context):
        mode = context.get_form_value('mode')
        if mode == 'tiny_mce':
            return '/;download'
        proxy = super(DBResource_AddImage, self)
        return proxy.get_resource_action(context)



class DBResource_AddMedia(DBResource_AddImage):

    element_to_add = 'media'
    browse_content_class = AddMedia_BrowseContent

    text_values = {'title': MSG(u'Insert media'),
       'browse': MSG(u'Browse and insert a Media from the workspace'),
       'extern': MSG(u'Type the URL of an external media'),
       'insert': None,
       'upload': MSG(u'Upload a media to the current folder and insert it:'),
       'method': ';add_media'}


    def get_configuration(self):
        return {
            'show_browse': True,
            'show_external': True,
            'show_insert': False,
            'show_upload': True}

