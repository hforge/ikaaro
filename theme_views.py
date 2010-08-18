# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Henry Obein <henry@itaapy.com>
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
from itools.datatypes import DateTime, PathDataType
from itools.gettext import MSG
from itools.web import ERROR, FormError

# Import from ikaaro
from autoform import timestamp_widget, ImageSelectorWidget
from file import Image
from messages import MSG_UNEXPECTED_MIMETYPE
from popup import DBResource_AddImage
from resource_views import DBResource_Edit



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
        # Check favicon
        path = form['favicon']
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
        path = form['logo']
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
