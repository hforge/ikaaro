import logging
import os
import time
import traceback

from itools.uri import Reference
from itools.web.router import RequestMethod
from itools.web.exceptions import HTTPError
from ikaaro.server import get_server

from starlette.types import Scope, Receive, Send
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ikaaro import constants


log = logging.getLogger("ikaaro.web")

class ASGIApplication:
    def __init__(self):
        self.server = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            raise NotImplementedError("Only HTTP requests are supported")

        t0 = time.time()
        self.server = get_server()
        request = Request(scope, receive)
        method = request.method
        path = request.url.path
        read_only_method = method in ("GET", "OPTIONS")
        root = self.server.root
        GET_writable_paths = root.get_GET_writable_paths()
        rw_path = any(s in path for s in GET_writable_paths)
        read_only = read_only_method and not rw_path

        async with self.server.database.init_context(commit_at_exit=False, read_only=read_only) as context:
            try:
                # Init context from ASGI scope
                await context.init_from_request(request, {
                    'REQUEST_METHOD': scope['method'],
                    'PATH_INFO': scope['path'],
                    'QUERY_STRING': scope['query_string'].decode('ascii') if scope['query_string'] else '',
                })

                # Handle the request
                RequestMethod.handle_request(context)

                t1 = time.time()
                # Compute request time
                context.request_time = t1 - t0
                #scope['extensions']['request_time'] = t1 - t0

                # Callback at end of request
                context.on_request_end()

                # Prepare response
                response = await self.prepare_response(context)
                await response(scope, receive, send)

            except HTTPError as e:
                RequestMethod.handle_client_error(e, context)
                response = await self.prepare_response(context)
                await response(scope, receive, send)
            except Exception:
                tb = traceback.format_exc()
                log.error(f"Internal error: {tb}", exc_info=True)
                context.set_default_response(500)
                response = await self.prepare_response(context)
                await response(scope, receive, send)

    async def prepare_response(self, context) -> Response:
        """Convert context to ASGI response"""
        data = context.entity
        status_code = context.status or 500
        headers = dict(context.header_response)

        if context.content_type:
            headers['content-type'] = context.content_type

        if isinstance(data, Reference):
            # Handle redirects or file references
            return Response(status_code=status_code, headers=headers)

        if isinstance(data, str):
            data = data.encode("utf-8")

        if data:
            headers['content-length'] = str(len(data))

        return Response(content=data, status_code=status_code, headers=headers)

# Ensure sessions folder exists
try:
    os.makedirs(constants.SESSIONS_FOLDER, exist_ok=True)
except OSError:
    pass

# Session configuration
#session_opts = {
#    "session_type": constants.SESSIONS_STORE_TYPE,
#    "session_url": constants.SESSIONS_URL,
#    "session_data_dir": constants.SESSIONS_FOLDER,
#    "session_cookie_expires": constants.SESSION_EXPIRE,
#    "session_timeout": constants.SESSION_TIMEOUT,
#    "session_cookie_domain": constants.SESSION_DOMAIN,
#    "session_cookie_path": "/",
#    "session_secure": constants.SESSION_SECURE,
#    "session_httponly": True,
#    "session_data_serializer": "json",
#    "session_auto": False,
#    "session_samesite": constants.SESSION_SAMESITE,
#    "session_key": constants.SESSION_KEY,
#}

# Create ASGI application
app = ASGIApplication()

# Wrap with Starlette's session middleware
app = SessionMiddleware(app,
    secret_key=os.getenv("SECRET_KEY", "default_secret_key"),
    domain=constants.SESSION_DOMAIN,
    https_only=constants.SESSION_SECURE,
    max_age=constants.SESSION_EXPIRE,
    same_site=constants.SESSION_SAMESITE,
)

# To automatically handle X-Forwarded headers
app = TrustedHostMiddleware(app, allowed_hosts=["*"])

application = app
