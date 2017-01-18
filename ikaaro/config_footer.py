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
from config import Configuration
from file_views import File_Edit
from webpage import WebPage


class Footer(WebPage):

    class_id = 'config-footer'
    class_title = MSG(u'Footer')
    class_description = MSG(u'Define the site footer.')
    class_icon48 = 'icons/48x48/footer.png'

    # Configuration
    config_name = 'footer'
    config_group = 'webmaster'

    # Views
    class_views = ['edit', 'externaledit', 'commit_log']
    edit = File_Edit(fields=['data'])


    def init_resource(self, **kw):
        body = """
        <html xmlns="http://www.w3.org/1999/xhtml">
        <body>
        <a href="/;powered_by">Powered by Ikaaro</a>
        </body>
        </html>
        """
        super(Footer, self).init_resource(data={'en': body}, **kw)



# Register
Configuration.register_module(Footer)
