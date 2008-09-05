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

# Import from itools
from itools.datatypes import String, Unicode
from itools.gettext import MSG
from itools.handlers import checkid
from itools.i18n import get_language_name
from itools.stl import stl
from itools.uri import Path
from itools.vfs import FileName
from itools.web import STLForm

# Import from ikaaro
from datatypes import FileDataType
from messages import *
from registry import get_object_class
from views import NewInstanceForm
from widgets import Breadcrumb, build_menu



class DBResourceNewInstance(NewInstanceForm):

    access = 'is_allowed_to_add'
    template = '/ui/base/new_instance.xml'
    query_schema = {
        'type': String}
    schema = {
        'name': String,
        'title': Unicode}


    def get_title(self, context):
        type = context.get_query_value('type')
        if not type:
            return MSG(u'Add resource').gettext()
        cls = get_object_class(type)
        class_title = cls.class_title.gettext()
        title = MSG(u'Add $class_title')
        return title.gettext(class_title=class_title)


    def get_namespace(self, resource, context):
        type = context.query['type']
        cls = get_object_class(type)
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

        # Create the object
        class_id = context.query['type']
        cls = get_object_class(class_id)
        object = cls.make_object(cls, resource, name)
        # The metadata
        metadata = object.metadata
        language = resource.get_content_language(context)
        metadata.set_property('title', title, language=language)

        goto = './%s/' % name
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)



class DBResourceEditMetadata(STLForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit Metadata')
    icon = 'metadata.png'
    template = '/ui/base/edit_metadata.xml'
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


    def get_right_menus(self, resource, context):
        # Multilingual
        site_root = resource.get_site_root()
        languages = site_root.get_property('website_languages')
        content_language = context.get_cookie('language')
        if content_language is None:
            content_language = languages[0]

        options = []
        for language in languages:
            title = get_language_name(language)
            if language == content_language:
                css_class = 'nav_active'
            else:
                css_class = None
            options.append({
                'href': context.uri.replace(language=language),
                'title': title,
                'class': css_class,
            })

        # Ok
        return [{
            'title': MSG(u'Edit Language'),
            'content': build_menu(options)}]



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
        cls = get_object_class(mimetype)
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

        # Add the image to the object
        cls.make_object(cls, container, name, body, type=type)

        # Ok
        caption = MSG_CAPTION.gettext().encode('utf_8')
        if form['mode'] == 'wiki':
            scripts = ['/ui/wiki/javascript.js']
        else:
            scripts = ['/ui/tiny_mce/javascript.js',
                       '/ui/tiny_mce/tiny_mce_src.js',
                       '/ui/tiny_mce/tiny_mce_popup.js']

        object = container.get_resource(name)
        path = resource.get_pathto(object)
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
        # Add the file to the object
        class_id = context.get_form_value('type')
        cls = get_object_class(class_id)
        uri = cls.new_instance(cls, container, context)

        if ';add_link' not in uri.path:
            mode = context.get_form_value('mode', default='html')
            if mode == 'wiki':
                scripts = ['/ui/wiki/javascript.js']
            else:
                scripts = ['/ui/tiny_mce/javascript.js',
                           '/ui/tiny_mce/tiny_mce_src.js',
                           '/ui/tiny_mce/tiny_mce_popup.js']

            object = container.get_resource(uri.path[0])
            path = context.resource.get_pathto(object)
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

