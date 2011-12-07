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
from itools.datatypes import String
from itools.gettext import MSG
from itools.web import STLView

# Import from ikaaro
from autoform import MultilineWidget
from config import Configuration
from fields import Char_Field
from messages import MSG_CHANGES_SAVED
from resource_ import DBResource


class ConfigVHosts_Edit(STLView):

    access = 'is_admin'
    title = MSG(u'Virtual Hosts')
    description = MSG(u'Define the domain names for this Web Site.')
    template = '/ui/website/virtual_hosts.xml'
    schema = {'vhosts': String}


    def get_namespace(self, resource, context):
        vhosts = resource.get_value('vhosts')
        return {'vhosts': '\n'.join(vhosts)}


    def action(self, resource, context, form):
        vhosts = [ x.strip() for x in form['vhosts'].splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        resource.set_value('vhosts', vhosts)
        # Ok
        context.message = MSG_CHANGES_SAVED



class ConfigVHosts(DBResource):

    class_id = 'config-vhosts'
    class_title = MSG(u'Virtual Hosts')
    class_description = MSG(u'Define the domain names for this Web Site.')
    class_icon48 = 'icons/48x48/website.png'

    # Fields
    vhosts = Char_Field(multiple=True, title=MSG(u'Domain names'),
                        widget=MultilineWidget)

    # Views
    class_views = ['edit']
    edit = ConfigVHosts_Edit

    # Configuration
    config_name = 'vhosts'
    config_group = 'webmaster'


# Register
Configuration.register_module(ConfigVHosts)
