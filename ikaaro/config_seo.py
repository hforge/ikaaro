# -*- coding: UTF-8 -*-
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
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from config import Configuration
from fields import Char_Field
from resource_ import DBResource


seo_description = MSG(
    u'Optimize your website for better ranking in search engine results.')


class SEO(DBResource):

    class_id = 'config-seo'
    class_title = MSG(u'Search Engine Optimization')
    class_description = seo_description
    class_icon16 = 'icons/16x16/search.png'
    class_icon48 = 'icons/48x48/search.png'

    # Fields
    google_site_verification = Char_Field(
        title=MSG(u'Google site verification key'))
    yahoo_site_verification = Char_Field(
        title=MSG(u'Yahoo site verification key'))
    bing_site_verification = Char_Field(
        title=MSG(u'Bing site verification key'))


    # Views
    class_views = ['edit']
    edit = AutoEdit(title=MSG(u'Search engine optimization'),
                    description=seo_description,
                    fields=['google_site_verification',
                            'yahoo_site_verification',
                            'bing_site_verification'])

    # Configuration
    config_name = 'seo'
    config_group = 'webmaster'


# Register
Configuration.register_module(SEO)
