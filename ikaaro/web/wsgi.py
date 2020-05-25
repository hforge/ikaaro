# -*- coding: UTF-8 -*-
# Copyright (C) 2017 Sylvain Taverne <taverne.sylvain@gmail.com>
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

# Import from standard library
from time import time
import os

# Import from beaker
from beaker.middleware import SessionMiddleware

# Import from itools
from itools.log import log_error
from itools.web.router import RequestMethod
from itools.web.utils import reason_phrases
from itools.web.exceptions import HTTPError

from ikaaro.constants import SESSIONS_FOLDER, SESSIONS_STORE_TYPE
from ikaaro.constants import SESSION_EXPIRE, SESSION_TIMEOUT


def application(environ, start_response):
    from ikaaro.server import get_server
    t0 = time()
    server = get_server()
    with server.database.init_context(commit_at_exit=False) as context:
        try:
            # Init context from wsgi envrion
            context.init_from_environ(environ)
            # Handle the request
            RequestMethod.handle_request(context)
            t1 = time()
            # Compute request time
            context.request_time = t1-t0
            # Callback at end of request
            context.on_request_end()
        except HTTPError as e:
            RequestMethod.handle_client_error(e, context)
        except StandardError:
            log_error('Internal error', domain='itools.web')
            context.set_default_response(500)
        finally:
            headers =  context.header_response
            if context.content_type:
                headers.append(('Content-Type', context.content_type))
            if context.entity:
                headers.append(('Content-Length', str(len(context.entity))))
            status = context.status or 500
            status = '{0} {1}'.format(status, reason_phrases[status])
            start_response(str(status), headers)
            yield context.entity


try:
    os.makedirs(SESSIONS_FOLDER)
except OSError:
    pass

session_opts = {
    "session.type": SESSIONS_STORE_TYPE,
    "session.data_dir": SESSIONS_FOLDER,
    "session.cookie_expires": SESSION_EXPIRE,
    "session.timeout": SESSION_TIMEOUT,
    "session.cookie_path": "/",
    "session.secure": True,
    "session.httponly": True,
    "session.data_serializer": "json",
    "session.auto": False,
    "session.samesite": "Strict",
}


application = SessionMiddleware(application, session_opts)


def get_wsgi_application():
    return application
