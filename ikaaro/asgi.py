import logging
import os
import time
import traceback

# Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

# itools/ikaaro
from itools.uri import Reference
from itools.web.exceptions import HTTPError
from itools.web.router import RequestMethod
from ikaaro import constants
from ikaaro.server import get_server


log = logging.getLogger("ikaaro.web")

async def prepare_response(context) -> Response:
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

async def catch_all(request):
    scope = request.scope

    t0 = time.time()
    server = get_server()
    method = request.method
    path = request.url.path
    read_only_method = method in ("GET", "OPTIONS")
    root = server.root
    GET_writable_paths = root.get_GET_writable_paths()
    rw_path = any(s in path for s in GET_writable_paths)
    read_only = read_only_method and not rw_path

    async with server.database.init_context(commit_at_exit=False, read_only=read_only) as context:
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
            return await prepare_response(context)

        except HTTPError as e:
            RequestMethod.handle_client_error(e, context)
            return await prepare_response(context)
        except Exception:
            tb = traceback.format_exc()
            log.error(f"Internal error: {tb}", exc_info=True)
            context.set_default_response(500)
            return await prepare_response(context)


middleware = [
    Middleware(
        TrustedHostMiddleware,
        allowed_hosts=['*'],
    ),
    Middleware(
        SessionMiddleware,
        secret_key=os.getenv("SECRET_KEY", "default_secret_key"),
        domain=constants.SESSION_DOMAIN,
        https_only=constants.SESSION_SECURE,
        max_age=constants.SESSION_EXPIRE,
        same_site=constants.SESSION_SAMESITE,
    ),
]

routes = [
    Route("/{path:path}", catch_all, methods=['GET', 'POST']),  # XXX PUT, PATCH?
]
app = Starlette(middleware=middleware, routes=routes)
