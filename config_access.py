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
from itools.web import STLForm

# Import from ikaaro
from config import Configuration
from messages import MSG_CHANGES_SAVED
from resource_ import DBResource


class ConfigAccess_Edit(STLForm):

    access = 'is_admin'
    template = '/ui/website/security_policy.xml'
    schema = {
        'security_policy': String(default='intranet')}


    def get_namespace(self, resource, context):
        security_policy = resource.get_property('security_policy')
        return {
            'intranet': security_policy == 'intranet',
            'extranet': security_policy == 'extranet',
            'community': security_policy == 'community'}


    def action(self, resource, context, form):
        resource.set_property('security_policy', form['security_policy'])
        context.message = MSG_CHANGES_SAVED



class ConfigAccess(DBResource):

    class_id = 'config-access'
    class_version = '20110606'
    class_title = MSG(u'Access Control')
    class_description = MSG(u'Choose the security policy.')
    class_icon48 = 'icons/48x48/lock.png'

    class_schema = merge_dicts(
        DBResource.class_schema,
        security_policy=String(source='metadata', default='intranet'))

    # Views
    class_views = ['edit']
    edit = ConfigAccess_Edit()

    # Configuration
    config_name = 'access'
    config_group = 'access'


Configuration.register_plugin(ConfigAccess)
