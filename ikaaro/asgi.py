import contextlib
import logging
import os
import time
import traceback

# Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.applications import Starlette
from starlette.responses import Response, JSONResponse
from starlette.routing import Route

# itools/ikaaro
from itools.database import RWDatabase
from itools.uri import Reference
from itools.web.exceptions import HTTPError
from itools.web.router import RequestMethod
from ikaaro import constants
from ikaaro.server import get_server


#
# Ikaaro: bridge from Starlette to Ikaaro
#

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
    t0 = time.time()
    server = get_server()

    # read-only or read-write
    method = request.method
    path = request.url.path
    read_only_method = method in ("GET", "OPTIONS")
    GET_writable_paths = server.root.get_GET_writable_paths()
    rw_path = any(s in path for s in GET_writable_paths)
    read_only = read_only_method and not rw_path

    async with server.database.init_context(commit_at_exit=False, read_only=read_only) as context:
        try:
            # Init context from Starlette's request
            await context.init_from_request(request)

            # Handle the request
            RequestMethod.handle_request(context)

            # Compute request time
            context.request_time = time.time() - t0

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


#
# Starlette routes
#

async def ctrl(request):
    server = get_server()
    async with server.database.init_context() as context:
        resource = server.root
        database = context.database
        return JSONResponse({
            'packages': resource.get_version_of_packages(context),
            'read-only': not isinstance(database, RWDatabase),
        })


#
# Starlette application
#

@contextlib.asynccontextmanager
async def lifespan(app):
    # TODO Launch the cron-like task here
    print("Run at startup!")
    yield
    print("Run on shutdown!")

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
    Route('/;_ctrl', ctrl),
    Route("/{path:path}", catch_all, methods=['GET', 'POST']),  # XXX PUT, PATCH?
]

app = Starlette(lifespan=lifespan, middleware=middleware, routes=routes)
