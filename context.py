# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.web import WebContext

# Import from ikaaro
from ikaaro.globals import spool


class CMSContext(WebContext):

    def get_template(self, path):
        from ikaaro.boot import ui
        return ui.get_template(path)


    def send_email(self, to_addr, subject, from_addr=None, text=None,
                   html=None, encoding='utf-8', subject_with_host=True,
                   return_receipt=False):

        # From address
        if from_addr is None and self.user:
            from_addr = user.get_property('email')

        # Subject
        if subject_with_host:
            subject = u'[%s] %s' % (self.uri.authority, subject)

        spool.send_email(to_addr, subject, from_addr=from_addr, text=text,
                        html=html, encoding=encoding,
                        return_receipt=return_receipt)

