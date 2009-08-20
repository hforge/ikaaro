# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 David Versmisse <david.versmisse@itaapy.com>
# Copyright (C) 2008 Henry Obein <henry@itaapy.com>
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

# Import from the Standard Library
import sys

# Import from pygobject
from glib import GError

# Import from itools
from itools.fs import vfs
from itools.http import HTTPServer, set_context
from itools.soup import SoupMessage
from itools.web import WebContext

# Import from ikaaro
from utils import is_pid_running


def ask_confirmation(message, confirm=False):
    if confirm is True:
        print message + 'Y'
        return True

    sys.stdout.write(message)
    sys.stdout.flush()
    line = sys.stdin.readline()
    line = line.strip().lower()
    return line == 'y'



def get_pid(target):
    try:
        pid = open('%s/pid' % target).read()
    except IOError:
        return None

    pid = int(pid)
    if is_pid_running(pid):
        return pid
    return None



def get_fake_context():
    soup_message = SoupMessage()
    context = WebContext(soup_message, '/')
    set_context(context)
    return context


class CMSServer(HTTPServer):

    def is_running_in_rw_mode(self):
        url = 'http://localhost:%s/;_ctrl?name=read-only' % self.port
        try:
            h = vfs.open(url)
        except GError:
            # The server is not running
            return False

        return h.read() == 'no'

