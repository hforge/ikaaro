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
from itools.core import merge_dicts
from itools.datatypes import String
from itools.gettext import MSG

# Import from ikaaro
from autoedit import AutoEdit
from config import Configuration
from resource_ import DBResource


seo_description = MSG(
    u'Optimize your website for better ranking in search engine results.')
site_verification = String(source='metadata', default='')


class SEO(DBResource):

    class_id = 'config-seo'
    class_version = '20110606'
    class_title = MSG(u'Search Engine Optimization')
    class_description = seo_description
    class_icon16 = 'icons/16x16/search.png'
    class_icon48 = 'icons/48x48/search.png'
    class_views = ['edit']

    class_schema = merge_dicts(
        DBResource.class_schema,
        # Metadata
        google_site_verification=site_verification(
            title=MSG(u'Google site verification key')),
        yahoo_site_verification=site_verification(
            title=MSG(u'Yahoo site verification key')),
        bing_site_verification=site_verification(
            title=MSG(u'Bing site verification key')))


    edit = AutoEdit(title=MSG(u'Search engine optimization'),
                    description=seo_description,
                    fields=['google_site_verification',
                            'yahoo_site_verification',
                            'bing_site_verification'])


# Register
Configuration.register_plugin('seo', SEO)