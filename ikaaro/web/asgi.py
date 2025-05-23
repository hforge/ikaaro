import os
import time
import traceback
from logging import getLogger

from itools.uri import Reference
from itools.web.router import RequestMethod
from itools.web.utils import reason_phrases
from itools.web.exceptions import HTTPError
from ikaaro.server import get_server

from starlette.types import Scope, Receive, Send
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.sessions import SessionMiddleware

from ikaaro.constants import (
    SESSIONS_FOLDER, SESSIONS_STORE_TYPE, SESSION_EXPIRE, SESSION_TIMEOUT,
    SESSION_DOMAIN, SESSION_SAMESITE, SESSION_KEY, SESSIONS_URL, SESSION_SECURE
)

log = getLogger("ikaaro.web")

class ASGIApplication:
    def __init__(self):
        self.server = None
        self.session_middleware = None

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

        with self.server.database.init_context(commit_at_exit=False, read_only=read_only) as context:
            try:
                # Init context from ASGI scope
                await self.init_context_from_scope(context, scope, request)
                
                # Handle the request
                await RequestMethod.handle_request(context)
                
                t1 = time.time()
                # Compute request time
                context.request_time = t1 - t0
                scope['extensions']['request_time'] = t1 - t0
                
                # Callback at end of request
                context.on_request_end()
                
                # Prepare response
                response = await self.prepare_response(context)
                await response(scope, receive, send)
                
            except HTTPError as e:
                await RequestMethod.handle_client_error(e, context)
                response = await self.prepare_response(context)
                await response(scope, receive, send)
            except Exception:
                tb = traceback.format_exc()
                log.error(f"Internal error: {tb}", exc_info=True)
                context.set_default_response(500)
                response = await self.prepare_response(context)
                await response(scope, receive, send)

    async def init_context_from_scope(self, context, scope: Scope, request: Request):
        """Initialize context from ASGI scope"""
        # Convert ASGI request to context format
        # You'll need to adapt this to your specific context initialization needs
        environ = {
            'REQUEST_METHOD': scope['method'],
            'PATH_INFO': scope['path'],
            'QUERY_STRING': scope['query_string'].decode('ascii') if scope['query_string'] else '',
            'wsgi.input': request.stream(),
            # Add other necessary environ variables
        }
        context.init_from_environ(environ)

    async def prepare_response(self, context) -> Response:
        """Convert context to ASGI response"""
        data = context.entity
        status_code = context.status or 500
        status_text = reason_phrases.get(status_code, 'Unknown Status')
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
        
        return Response(
            content=data,
            status_code=f"{status_code} {status_text}",
            headers=headers
        )

# Ensure sessions folder exists
try:
    os.makedirs(SESSIONS_FOLDER, exist_ok=True)
except OSError:
    pass

# Session configuration
session_opts = {
    "session_type": SESSIONS_STORE_TYPE,
    "session_url": SESSIONS_URL,
    "session_data_dir": SESSIONS_FOLDER,
    "session_cookie_expires": SESSION_EXPIRE,
    "session_timeout": SESSION_TIMEOUT,
    "session_cookie_domain": SESSION_DOMAIN,
    "session_cookie_path": "/",
    "session_secure": SESSION_SECURE,
    "session_httponly": True,
    "session_data_serializer": "json",
    "session_auto": False,
    "session_samesite": SESSION_SAMESITE,
    "session_key": SESSION_KEY,
}

# Create ASGI application
asgi_app = ASGIApplication()

# Wrap with Starlette's session middleware
application = SessionMiddleware(
    asgi_app,
    secret_key=os.getenv("SECRET_KEY", "default_secret_key"),
    session_cookie="session",
    **session_opts
)

def get_asgi_application():
    return application
