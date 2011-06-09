# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Henry Obein <henry@itaapy.com>
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.core import merge_dicts, get_abspath
from itools.datatypes import DateTime, PathDataType, URI
from itools.gettext import MSG
from itools.handlers import ro_database, File as FileHandler
from itools.web import ERROR, FormError

# Import from ikaaro
from autoform import timestamp_widget, ImageSelectorWidget
from config import Configuration
from file import Image
from folder import Folder
from folder_views import GoToSpecificDocument
from messages import MSG_UNEXPECTED_MIMETYPE
from popup import DBResource_AddImage
from resource_views import DBResource_Edit
from text import CSS


###########################################################################
# Views
###########################################################################
class Theme_AddFavIcon(DBResource_AddImage):

    element_to_add = 'favicon'
    item_classes = (Image,) # FIXME Should be ICO

    def get_root(self, context):
        return context.resource


    def get_configuration(self):
        return {
            'show_browse': True,
            'show_external': False,
            'show_insert': False,
            'show_upload': True}


    def is_item(self, resource):
        if isinstance(resource, Image):
            mimetype = resource.handler.get_mimetype()
            width, height = resource.handler.get_size()
            # Check the size, max 32x32
            if mimetype == 'image/x-icon' and \
                    width <= 32 and height <= 32:
                return True
        return False



class Theme_AddLogo(DBResource_AddImage):

    element_to_add = 'favicon'
    item_classes = (Image,)

    def get_root(self, context):
        return context.resource


    def get_configuration(self):
        return {
            'show_browse': True,
            'show_external': False,
            'show_insert': False,
            'show_upload': True}



class Theme_Edit(DBResource_Edit):

    context_menus = []
    schema = {
            'timestamp': DateTime(readonly=True),
            'favicon': PathDataType,
            'logo': PathDataType}
    widgets = [ timestamp_widget,
                ImageSelectorWidget('favicon', action='add_favicon',
                    title=MSG(u'Replace favicon file (ICO 32x32 only)')),
                ImageSelectorWidget('logo', action='add_logo',
                    title=MSG(u'Replace logo file')) ]

    def _get_form(self, resource, context):
        form = DBResource_Edit._get_form(self, resource, context)
        # Use form.get(xxx) because favicon and logo can be not defined
        # Check favicon
        path = form.get('favicon')
        if path:
            favicon = resource.get_resource(path, soft=True)
            if favicon is None:
                message = ERROR(u"The file \"{filename}\" doesn't exists.")
                raise FormError, message(filename=path)

            # Check favicon properties
            mimetype = favicon.handler.get_mimetype()
            if mimetype != 'image/x-icon':
                message = MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)
                raise FormError, message

            # Check the size, max 32x32
            width, height = favicon.handler.get_size()
            if width > 32 or height > 32:
                message = ERROR(u'Unexpected file of size {width}x{height}.')
                raise FormError, message(width=width, height=height)

        # Check logo
        path = form.get('logo')
        if path:
            image = resource.get_resource(path, soft=True)
            if image is None:
                message = ERROR(u"The file \"{filename}\" doesn't exists.")
                raise FormError, message(filename=path)

            if isinstance(image, Image) is False:
                mimetype = image.handler.get_mimetype()
                message = MSG_UNEXPECTED_MIMETYPE(mimetype=mimetype)
                return FormError, message

        return form


###########################################################################
# Resource
###########################################################################
class Theme(Folder):

    class_id = 'config-theme'
    class_title = MSG(u'Theme')
    class_description = MSG(u'Allow to customize ikaaro skin')
    class_icon48 = 'icons/48x48/theme.png'
    __fixed_handlers__ = ['style']

    class_schema = merge_dicts(
        Folder.class_schema,
        # Metadata
        favicon=URI(source='metadata', default=''),
        logo=URI(source='metadata', default=''))


    def init_resource(self, **kw):
        Folder.init_resource(self, **kw)
        # CSS file
        path = get_abspath('ui/themes/style.css')
        body = open(path).read()
        self.make_resource('style', CSS, extension='css', body=body,
                           state='public')
        # Logo
        path = get_abspath('ui/themes/logo.png')
        image = ro_database.get_handler(path, FileHandler)
        self.make_resource('logo', Image, body=image.to_str(),
                           extension='png', filename='logo.png',
                           format='image/png', state='public')
        self.set_property('logo', 'logo')
        # Banner
        path = get_abspath('ui/themes/banner.jpg')
        image = ro_database.get_handler(path, FileHandler)
        self.make_resource('banner', Image, body=image.to_str(),
                           extension='jpg', filename='banner.jpg',
                           format='image/jpeg', state='public')

    # Views
    class_views = ['edit', 'edit_css', 'browse_content', 'preview_content',
                   'links', 'backlinks', 'commit_log']

    add_favicon = Theme_AddFavIcon()
    add_logo = Theme_AddLogo()
    edit = Theme_Edit()
    edit_css = GoToSpecificDocument(specific_document='style',
            access='is_allowed_to_edit', specific_view='edit',
            title=MSG(u'Edit CSS'))

    # Configuration
    config_name = 'theme'
    config_group = 'webmaster'



###########################################################################
# Register
###########################################################################
Configuration.register_plugin(Theme)
