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

from datetime import datetime, timedelta
from email.parser import BytesHeaderParser
from importlib import import_module
from io import BytesIO
from os import fdopen, getpgid, getpid, kill, mkdir, remove, path
from os.path import join
from signal import SIGINT, SIGTERM
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from tempfile import mkstemp
from time import strftime, time
from traceback import format_exc
from wsgiref.util import setup_testing_defaults
import fcntl
import inspect
import json
import logging
import pathlib
import pickle
import sys

# Requirements
from gevent.lock import BoundedSemaphore
from gevent.pywsgi import WSGIServer, WSGIHandler
from gevent.signal import signal as gevent_signal
from jwcrypto.jwk import JWK
from psutil import pid_exists
from requests import Request

# Import from itools
from itools.core import become_daemon, vmsize
from itools.database import Metadata, RangeQuery
from itools.database import make_database, get_register_fields
from itools.database.backends.catalog import make_catalog
from itools.datatypes import Boolean, Email, Integer, String, Tokens
from itools.fs import lfs
from itools.handlers import ConfigFile
from itools.loop import cron
from itools.uri import get_reference, get_uri_path, Path
from itools.web import set_context, get_context
from itools.web.dispatcher import URIDispatcher
from itools.web.router import RequestMethod

# Import from ikaaro.web
from .database import get_database
from .datatypes import ExpireValue
from .log import config_logging
from .views import CachedStaticView
from .skins import skin_registry
from .views import IkaaroStaticView


log_ikaaro = logging.getLogger("ikaaro")
log_access = logging.getLogger("ikaaro.access")
log_cron = logging.getLogger("ikaaro.cron")


SMTP_SEND_SEM = BoundedSemaphore(1)

class SMTPSendManager:

    def __enter__(self):
        SMTP_SEND_SEM.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        SMTP_SEND_SEM.release()


template = (
"""# The "modules" variable lists the Python modules or packages that will be
# loaded when the applications starts.
#
modules = {modules}

# The "listen-address" and "listen-port" variables define, respectively, the
# internet address and the port number the web server listens to for HTTP
# connections.
#
# These variables are required (i.e. there are not default values).  To
# listen from any address write the value '*'.
#
listen-address = {listen_address}
listen-port = {listen_port}

# The "smtp-host" variable defines the name or IP address of the SMTP relay.
# The "smtp-from" variable is the email address used in the From field when
# sending anonymous emails.  (These options are required for the application
# to send emails).
#
# The "smtp-login" and "smtp-password" variables define the credentials
# required to access a secured SMTP server.
#
smtp-host = {smtp_host}
smtp-from = {smtp_from}
smtp-login =
smtp-password =

# The "log-level" variable may have one of these values (from lower to
# higher verbosity): 'critical' 'error', 'warning', 'info' and 'debug'.
# The default is 'warning'.
#
# If the "log-email" address is defined error messages will be sent to it.
#
log-level = warning
log-email = {log_email}

# The "cron-interval" variable defines the number of seconds between every
# call to the cron job manager. If zero (the default) the cron job won't be
# run at all.
#
cron-interval = 60

# If the "session-timeout" variable is different from zero (the default), the
# user will be automatically logged out after the specified number of minutes.
#
session-timeout = 0

# The "database-size" variable defines the number of file handlers to store
# in the database cache.  It is made of two numbers, the upper limit and the
# bottom limit: when the cache size hits the upper limit, handlers will be
# removed from the cache until it hits the bottom limit.
#
# The "database-readonly" variable, when set to 1 starts the database in
# read-only mode, all write operations will fail.
#
database-size = {size_min}:{size_max}
database-readonly = 0

# The "index-text" variable defines whether the catalog must process full-text
# indexing. It requires (much) more time and third-party applications.
# To speed up catalog updates, set this option to 0 (default is 1).
#
index-text = 1

# The "accept-cors" variable defines whether the web server accept
# cross origin requests or not.
# To accept cross origin requests, set this option to 1 (default is 1)
#
accept-cors = 1

# The size of images can be controlled by setting the following values.
# (ie. max-width = 1280) (by default it is None, keeping original size).
#
max-width =
max-height =

# Allow to customize wsgi application
wsgi_application = ikaaro.web.wsgi
""")


def ask_confirmation(message, confirm=False):
    if confirm is True:
        print(message + 'Y')
        return True

    sys.stdout.write(message)
    sys.stdout.flush()
    line = sys.stdin.readline()
    line = line.strip().lower()
    return line == 'y'


def load_modules(config):
    """Load Python packages and modules.
    """
    modules = config.get_value('modules')
    for name in modules:
        name = name.strip()
        __import__(name)


def get_pid(target):
    try:
        pid = open(target).read()
    except OSError:
        return None

    pid = int(pid)
    try:
        getpgid(pid)
    except OSError:
        return None
    return pid


def stop_server(target):
    log_ikaaro.info("Stoping server...")
    pid = get_pid(f'{target}/pid')
    if pid:
        kill(pid, SIGTERM)


def get_root(database):
    metadata = database.get_handler('.metadata', cls=Metadata)
    cls = database.get_resource_class(metadata.format)
    return cls(abspath=Path('/'), database=database, metadata=metadata)



def create_server(target, email, password, root,
                  backend='git', modules=None,
                  listen_port='8080', listen_address='127.0.0.1',
                  smtp_host='localhost',
                  log_email=None, website_languages=None,
                  size_min=19500, size_max=20500):
    from .root import Root
    modules = modules or []
    # Get modules
    for module in modules:
        exec(f'import {module}')
    # Load the root class
    if root is None:
        root_class = Root
    else:
        modules.insert(0, root)
        mod = __import__(root)
        root_class = getattr(mod, 'Root')
    # Make folder
    try:
        mkdir(target)
    except OSError:
        raise ValueError('can not create the instance (check permissions)')

    # The configuration file
    config = template.format(
        modules=" ".join(modules),
        listen_port=listen_port or '8080',
        listen_address=listen_address or '127.0.0.1',
        smtp_host=smtp_host or 'localhost',
        smtp_from=email,
        size_min=size_min,
        size_max=size_max,
        log_email=log_email)
    with open(f'{target}/config.conf', 'w') as file:
        file.write(config)

    # Create database
    database = make_database(target, size_min, size_max, backend=backend)
    database.close()
    database = get_database(target, size_min, size_max, backend=backend)

    # Create the folder structure
    mkdir(f'{target}/log')
    mkdir(f'{target}/spool')

    # Make the root
    with database.init_context() as context:
        metadata = Metadata(cls=root_class)
        database.set_handler('.metadata', metadata)
        root = root_class(abspath=Path('/'), database=database, metadata=metadata)
        # Language
        language_field = root_class.get_field('website_languages')
        website_languages = website_languages or language_field.default
        root.set_value('website_languages', website_languages)
        context.database.save_changes()
    # Re-init context with context cls
    with database.init_context() as context:
        # Init root resource
        root.init_resource(email, password)
        # Set mtime
        root.set_property('mtime', context.timestamp)
        # Save changes
        database.save_changes('Initial commit')
        database.close()
    # Empty context
    set_context(None)


server = None
def get_server():
    return server


def set_server(the_server):
    global server
    if the_server and get_server() is not None:
        raise ValueError('Server is already defined')
    server = the_server


class ServerHandler(WSGIHandler):

    def format_request(self):
        now = datetime.now().replace(microsecond=0)
        length = self.response_length or '-'

        request_time = self.environ.get('REQUEST_TIME')
        delta = f"{request_time:.6f}" if request_time else '-'

        address = self.environ.get('HTTP_X_FORWARDED_FOR') or '-'
        request = self.requestline or ''

        # (Is that really necessary? At least there's no overhead.)
        # Use the native string version of the status, saved so we don't have to
        # decode. But fallback to the encoded 'status' in case of subclasses
        status = (self._orig_status or self.status or '000').split()[0]

        return f'{address} - - [{now}] "{request}" {status} {length} {delta}'

    def headers_bytes_to_str(self, data: dict):
        # WSGI encodes in latin-1
        # https://github.com/gevent/gevent/blob/master/src/gevent/pywsgi.py#L859=
        new_response_headers = {}
        for key, value in data.items():
            if type(key) is bytes:
                key = key.decode("latin-1")
            if type(value) is bytes:
                value = value.decode("latin-1")
            new_response_headers[key] = value
        return new_response_headers


class Server:

    timestamp = None
    port = None
    environment = {}
    modules = []
    database = None
    session_timeout = timedelta(0)
    accept_cors = False
    dispatcher = URIDispatcher()
    wsgi_server = None
    cron_statistics = {}


    def __init__(self, target, read_only=False, cache_size=None, port=None, detach=False):
        set_server(self)

        # Set instance variables
        self.timestamp = str(int(time() / 2))
        self.target = lfs.get_absolute_path(target)
        self.read_only = read_only
        self.detach = detach

        # Load the config
        config = self.load_config()

        # Logging
        log_level = config.get_value('log-level').upper()
        logdir = pathlib.Path(self.target) / 'log'
        config_logging(logdir, log_level, detach)

        # Load modules
        load_modules(config)
        self.modules = config.get_value('modules')
        # Find out the port to listen
        if port:
            self.port = int(port)
        else:
            self.port = config.get_value('listen-port')
        # Contact Email
        self.smtp_from = config.get_value('smtp-from')

        # Full-text indexing
        self.index_text = config.get_value('index-text', type=Boolean, default=True)
        # Accept cors
        self.accept_cors = config.get_value(
            'accept-cors', type=Boolean, default=False)

        # The database
        if cache_size is None:
            cache_size = config.get_value('database-size')
        if ':' in cache_size:
            size_min, size_max = cache_size.split(':')
        else:
            size_min = size_max = cache_size
        size_min, size_max = int(size_min), int(size_max)
        read_only = read_only or config.get_value('database-readonly')
        # Get database
        database = get_database(target, size_min, size_max, read_only)
        self.database = database
        # Find out the root class
        root = get_root(database)
        self.root = root
        # Load environment file
        root_file_path = inspect.getfile(root.__class__)
        environement_path = str(get_reference(root_file_path).resolve('environment.json'))
        if lfs.exists(environement_path):
            with open(environement_path) as f:
                data = f.read()
                self.environment = json.loads(data)
        # Useful the current uploads stats
        self.upload_stats = {}

        # Email service
        self.spool = lfs.resolve2(self.target, 'spool')
        spool_failed = f'{self.spool}/failed'
        if not lfs.exists(spool_failed):
            lfs.make_folder(spool_failed)
        # Configuration variables
        get_value = config.get_value
        self.smtp_host = get_value('smtp-host')
        self.smtp_login = get_value('smtp-login', default='').strip()
        self.smtp_password = get_value('smtp-password', default='').strip()
        # Email is sent asynchronously
        self.flush_spool()
        # Logging events
        # Session timeout
        self.session_timeout = get_value('session-timeout')
        # Register routes
        self.register_dispatch_routes()
        # Register JWT key
        self.JWK_SECRET = self.get_JWT_key()


    def get_JWT_key_path(self):
        target = self.target
        return path.join(target, "jwt_key.PEM")


    def get_JWT_key(self):
        key_path = self.get_JWT_key_path()
        try:
            with open(key_path, mode="rb") as key_file:
                lines = key_file.readlines()
                key_pem_string = b"".join(lines)
                jwk = JWK.from_pem(key_pem_string)
        except OSError:
            # No pem file found generating one
            jwk = self.generate_JWT_key()
            self.save_JWT_key(jwk)
        return jwk


    def save_JWT_key(self, jwk):
        key_path = self.get_JWT_key_path()
        with open(key_path, mode="wb") as key_file:
            key_pem_string = jwk.export_to_pem(private_key=True, password=None)
            key_file.write(key_pem_string)


    def generate_JWT_key(self):
        jwk = JWK(generate="RSA", size=4096)
        return jwk


    def load_config(self):
        self.config = get_config(self.target)
        return self.config


    def set_cron_interval(self, interval, context):
        # Save new value into config
        self.config.set_value('cron-interval', interval)
        self.config.save_state()
        # Reload config
        self.load_config()
        # Relaunch cron if it was desactivated ?
        if interval > 0 and not self.cron_statistics['started']:
            self.launch_cron(context)


    def get_database(self):
        database = self.database
        # Reopen so if we have one readonly request it will works
        database.backend.catalog._db.reopen()
        # Ok
        return database


    def check_consistency(self, quick):
        log_ikaaro.info("Check database consistency")
        # Check the server is not running
        if self.read_only:
            pid = get_pid(f'{self.target}/pid_ro')
        else:
            pid = get_pid(f'{self.target}/pid')
        if pid is not None:
            log_ikaaro.error(f'[{self.target}] The Web Server is already running.')
            return False
        # Ok
        return True


    def start(self):
        target = pathlib.Path(self.target)

        # Daemon mode
        if self.detach:
            log_ikaaro.info('Daemonize..')
            become_daemon()

        # Find out the IP to listen to
        address = self.config.get_value('listen-address').strip()
        if not address:
            raise ValueError('listen-address is missing from config.conf')
        # Check port
        if self.port is None:
            raise ValueError('listen-port is missing from config.conf')

        # Save PID
        pid = getpid()
        (target / 'pid').write_text(str(pid))
        # Call method on root at start
        with self.database.init_context() as context:
            context.root.launch_at_start(context)
            if not self.read_only:
                self.launch_cron(context)
        # Listen & set context
        self.listen(address, self.port)

        # XXX The interpreter do not go here
        #self.server.root.launch_at_stop(context)
        ## Ok
        return True


    def launch_cron(self, context):
        # Set cron interval
        interval = self.config.get_value('cron-interval')
        if interval:
            # Statistics
            next_start = context.timestamp + timedelta(seconds=interval)
            self.cron_statistics = {'last_start': None,
                                    'last_end': None,
                                    'next_start': next_start,
                                    'started': True}
            # Launch
            cron(self.cron_manager, interval)
        else:
            self.cron_statistics['started'] = False


    def reindex_catalog(self, quiet=False, quick=False, as_test=False):
        # FIXME: should be moved into backend
        log_ikaaro.info(f'reindex catalog {quiet} {quick} {as_test}')
        if self.is_running_in_rw_mode():
            log_ikaaro.error("Cannot proceed, the server is running in read-write mode.")
            return
        # Create a temporary new catalog
        catalog_path = f'{self.target}/catalog.new'
        if lfs.exists(catalog_path):
            lfs.remove(catalog_path)
        catalog = make_catalog(catalog_path, get_register_fields())
        # Get the root
        root = self.root
        # Update
        t0, v0 = time(), vmsize()
        doc_n = 0
        error_detected = False
        with self.database.init_context() as context:
            for obj in root.traverse_resources():
                if not quiet or doc_n % 10000 == 0:
                    log_ikaaro.info(f'{doc_n} {obj.abspath}')
                doc_n += 1
                context.resource = obj
                values = obj.get_catalog_values()
                # Index the document
                try:
                    catalog.index_document(values)
                except Exception:
                    if as_test:
                        error_detected = True
                        log_ikaaro.error(f"Error, Abspath of the resource: {str(obj.abspath)}")
                    else:
                        raise
                # Free Memory
                del obj
                self.database.make_room()

        if not error_detected:
            if as_test:
                # Delete the empty log file
                remove(f'{self.target}/log/update-catalog')

            # Update / Report
            t1, v1 = time(), vmsize()
            v = (v1 - v0)/1024
            log_ikaaro.info(f"[Update] Time: {t1 - t0:.02f} seconds. Memory: {v} Kb")
            # Commit
            log_ikaaro.info("[Commit]")
            catalog.save_changes()
            catalog.close()
            # Commit / Replace
            old_catalog_path = f'{self.target}/catalog'
            if lfs.exists(old_catalog_path):
                lfs.remove(old_catalog_path)
            lfs.move(catalog_path, old_catalog_path)
            # Commit / Report
            t2, v2 = time(), vmsize()
            v = (v2 - v1)/1024
            log_ikaaro.info(f"Time: {t2 - t1:.02f} seconds. Memory: {v} Kb")
            return True
        else:
            log_ikaaro.error("[Update] Error(s) detected, the new catalog was NOT saved")
            log_ikaaro.info(f"[Update] You can find more infos in {join(self.target, 'log/update-catalog')!r}")
            return False


    def get_pid(self):
        return get_pid(f'{self.target}/pid')


    def is_running(self):
        pid = self.get_pid()
        if pid:
            return pid_exists(pid)
        else:
            return False


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        set_server(None)


    def close(self):
        log_ikaaro.info("Close server")
        self.database.close()


    def stop(self, force=False):
        log_ikaaro.info("Stoping server...")
        # Stop wsgi server
        if self.wsgi_server:
            self.wsgi_server.stop()
        # Close database
        self.close()


    def stop_signal(self, signal, handler):
        self.stop()


    def listen(self, address, port):
        log_ikaaro.info(f"Listen {address}:{port}")

        self.port = port
        if address == '*':
            address = ''

        # Serve
        wsgi_module = self.config.get_value("wsgi_application")
        wsgi_module = import_module(wsgi_module)
        application = getattr(wsgi_module, "application")
        listener = (address or '', port)
        self.wsgi_server = WSGIServer(listener, application,
                                      handler_class=ServerHandler,
                                      log=log_access,
        )
        gevent_signal(SIGTERM, self.stop_signal)
        gevent_signal(SIGINT, self.stop_signal)
        self.wsgi_server.serve_forever()


    def is_running_in_rw_mode(self, mode='running'):
        # FIXME
        is_running = self.is_running()
        if not is_running:
            return False
        if mode == 'request':
            raise NotImplementedError


    #######################################################################
    # Mailing
    #######################################################################
    def get_spool_size(self):
        spool = lfs.open(self.spool)
        # We have always a 'failed' directory => "-1"
        return len(spool.get_names()) - 1


    def save_email(self, message):
        # Check the SMTP host is defined
        if not self.smtp_host:
            raise ValueError('"smtp-host" is not set in config.conf')

        spool = lfs.resolve2(self.target, 'spool')
        tmp_file, tmp_path = mkstemp(dir=spool)
        file = fdopen(tmp_file, 'w')
        try:
            message = message.as_string()
            file.write(message)
        finally:
            file.close()


    def flush_spool(self):
        cron(self._smtp_send, timedelta(seconds=1))


    def send_email(self, message):
        self.save_email(message)
        self.flush_spool()


    def _smtp_send(self):
        with SMTPSendManager():
            nb_max_mails_to_send = 2
            spool = lfs.open(self.spool)

            def get_names():
                # Find out emails to send
                locks = set()
                names = set()
                for name in spool.get_names():
                    if name == 'failed':
                        # Skip "failed" special directory
                        continue
                    if name[-5:] == '.lock':
                        locks.add(name[:-5])
                    else:
                        names.add(name)
                names.difference_update(locks)
                return names

            # Send emails
            names = get_names()
            smtp_host = self.smtp_host
            for name in list(names)[:nb_max_mails_to_send]:
                # 1. Open connection
                try:
                    smtp = SMTP(smtp_host)
                except Exception:
                    self.smtp_log_error()
                    try:
                        spool.move(name, f'failed/{name}')
                    except FileNotFoundError:
                        continue
                    return 60 if get_names() else False
                log_ikaaro.info(f"CONNECTED to {smtp_host}")

                # 2. Login
                if self.smtp_login and self.smtp_password:
                    smtp.login(self.smtp_login, self.smtp_password)

                # 3. Send message
                try:
                    try:
                        message_file = spool.open(name)
                    except FileNotFoundError:
                        continue
                    try:
                        fcntl.flock(message_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        message_file.close()
                        continue
                    message = message_file.read()
                    message_file.close()
                    headers = BytesHeaderParser().parsebytes(message)
                    subject = headers['subject']
                    from_addr = headers['from']
                    to_addr = headers['to']
                    if not subject or not from_addr or not to_addr:
                        spool.move(name, f'failed/empty_{name}')
                        continue
                    # Remove
                    spool.remove(name)
                    # Log
                    log_ikaaro.info(f"Email '{subject}' sent from '{from_addr}' to '{to_addr}'")
                except SMTPRecipientsRefused:
                    # The recipient addresses has been refused
                    self.smtp_log_error()
                    spool.move(name, f'failed/{name}')
                except SMTPResponseException as excp:
                    # The SMTP server returns an error code
                    self.smtp_log_error()
                    spool.move(name, f'failed/{excp.smtp_code}_{name}')
                except Exception:
                    self.smtp_log_error()

                # 4. Close connection
                smtp.quit()

            # Is there something left?
            return 60 if get_names() else False


    def smtp_log_error(self):
        details = format_exc()
        log_ikaaro.error(f"Error sending email : {details}", exc_info=True)


    def register_dispatch_routes(self):
        # Dispatch base routes from ikaaro
        self.register_urlpatterns_from_package('ikaaro.urls')
        for module in reversed(self.modules):
            self.register_urlpatterns_from_package(f'{module}.urls')
        # UI routes for skin
        ts = self.timestamp
        for name in skin_registry:
            skin = skin_registry[name]
            mount_path = f'/ui/{name}'
            skin_key = skin.get_environment_key(self)
            view = IkaaroStaticView(local_path=skin_key, mount_path=mount_path)
            self.dispatcher.add('/ui/%s/{name:any}' % name, view)
            mount_path = f'/ui/cached/{ts}/{name}'
            view = CachedStaticView(local_path=skin_key, mount_path=mount_path)
            self.dispatcher.add('/ui/cached/{}/{}/{{name:any}}'.format(ts, name), view)


    def register_urlpatterns_from_package(self, package):
        urlpatterns = None
        try:
            module_imported = __import__(f"{package}")
            urlpatterns = module_imported.urls.urlpatterns
        except ImportError:
            return

        # Dispatch base routes from ikaaro
        for urlpattern_object in urlpatterns:
            for pattern, view in urlpattern_object.get_patterns():
                self.dispatcher.add(pattern, view)
                # Register the route on the class
                view.route = pattern


    def is_production_environment(self):
        return self.is_environment('production')


    def is_development_environment(self):
        return self.is_environment('development')


    def is_environment(self, name):
        return self.environment.get('environment', 'production') == name

    #######################################################################
    # Time events
    #######################################################################
    def cron_manager(self):
        database = self.database
        error = False
        # Build fake context
        with database.init_context() as context:
            start_dtime = context.timestamp
            context.is_cron = True
            context.git_message = '[CRON]'
            # Go
            t0 = time()
            catalog = database.catalog
            query = RangeQuery('next_time_event', None, context.timestamp)
            search = database.search(query)
            if not search:
                return self.config.get_value('cron-interval')
            nb = len(search)
            log_cron.info(f"Cron launched for {nb} resources")
            for brain in search.get_documents():
                tcron0 = time()
                payload = brain.next_time_event_payload
                if payload:
                    payload = pickle.loads(payload)
                resource = database.get_resource(brain.abspath)
                try:
                    resource.time_event(payload)
                except Exception:
                    # Log error
                    log_cron.error(f"Cron error\n{format_exc()}", exc_info=True)
                    context.root.alert_on_internal_server_error(context)
                    # Abort changes
                    database.abort_changes()
                    # With error
                    error = True
                    break
                # Reindex resource without committing
                values = resource.get_catalog_values()
                catalog.index_document(values)
                # Log
                tcron1 = time()
                log_cron.info(f"Done for {brain.abspath} in {tcron1 - tcron0} seconds")
            # Save changes
            if not error:
                try:
                    catalog.save_changes()
                    database.save_changes()
                except Exception:
                    log_cron.error(f"Cron error on save changes\n{format_exc()}", exc_info=True)
                    context.root.alert_on_internal_server_error(context)
            # Log into cron.log
            t1 = time()
            if not error:
                log_cron.info(f"[OK] Cron finished for {nb} resources in {t1 - t0} seconds")
            else:
                log_cron.error(f"[ERROR] Cron finished for {nb} resources in {t1 - t0} seconds")
            # Log into access.log
            now = strftime('%d/%b/%Y:%H:%M:%S %z')
            message = '127.0.0.1 - - [%s] "GET /cron HTTP/1.1" 200 1 %.3f\n'
            log_ikaaro.info(message % (now, t1-t0))
            end_dtime = context.timestamp
        # Again, and again
        cron_interval = self.config.get_value('cron-interval')
        # Cron statistics
        if cron_interval:
            next_start = context.timestamp + timedelta(seconds=cron_interval)
        else:
            next_start = None
        self.cron_statistics = {'last_start': start_dtime,
                                'last_end': end_dtime,
                                'started': cron_interval > 0,
                                'next_start': next_start}
        # Ok
        return cron_interval



    def do_request(self, method='GET', path='/', headers=None, body='',
            context=None, as_json=False, as_multipart=False, files=None, user=None):
        """Experimental method to do a request on the server"""
        path_info = get_uri_path(path)
        q_string = path.split('?')[-1]
        # Build base environ
        environ = {'PATH_INFO': path_info,
                   'REQUEST_METHOD': method,
                   'HTTP_X-Forwarded-Host': 'localhost/',
                   'HTTP_X_FORWARDED_PROTO': 'http',
                   'QUERY_STRING': q_string}
        setup_testing_defaults(environ)
        if files:
            as_multipart = True
        # Get request header / body
        if as_json:
            req = Request(
                method,
                f'http://localhost:8080{path}',
                json=body,
                headers=headers
            )
            prepped = req.prepare()
        elif as_multipart:
            req = Request(
                method,
                f'http://localhost:8080{path}',
                data=body,
                files=files,
                headers=headers
            )
            prepped = req.prepare()
        else:
            req = Request(
                method,
                f'http://localhost:8080{path}',
                data=body,
                headers=headers
            )
            prepped = req.prepare()
        # Build headers
        headers = [(key.lower(), value) for key, value in prepped.headers.items()]
        headers.append(('User-Agent', 'Firefox'))
        for key, value in headers:
            environ[f"HTTP_{key.upper().replace('-', '_')}"] = value
        # Set wsgi input body
        if prepped.body is not None:
            if type(prepped.body) is str:
                environ['wsgi.input'] = BytesIO(prepped.body.encode("utf-8"))
            else:
                environ['wsgi.input'] = BytesIO(prepped.body)
        else:
            environ['wsgi.input'] = BytesIO()
        # Set content length
        if prepped.body:
            environ['CONTENT_LENGTH'] = len(prepped.body)
        # Set accept
        if as_json:
            environ['CONTENT_TYPE'] = 'application/json'
            environ['HTTP_ACCEPT'] = 'application/json'
        elif as_multipart:
            environ['CONTENT_TYPE'] = prepped.headers['Content-Type']
        else:
            environ['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        # Get context
        context = get_context()
        # Log user
        user = context.user or user
        if user:
            context.login(user)
            context.user = user
        context.server = self
        # Init context from environ
        context.init_from_environ(environ, user)
        # Do request
        RequestMethod.handle_request(context)
        # Transform result
        if context.entity is None:
            response = None
        elif as_json and not str(context.status).startswith('3'):
            # Do not load json if 302 (url redirection)
            try:
                response = json.loads(context.entity)
            except ValueError:
                msg = f'Cannot load json {context.entity}'
                raise ValueError(msg)
        else:
            response = context.entity
        # Commit
        if method == 'POST':
            context.database.save_changes()
        # Return result
        return {'status': context.status,
                'method': context.method,
                'entity': response,
                'context': context}



class ServerConfig(ConfigFile):

    schema = {
        'modules': Tokens,
        'listen-address': String(default=''),
        'listen-port': Integer(default=None),
        # Mailing
        'smtp-host': String(default=''),
        'smtp-from': String(default=''),
        'smtp-login': String(default=''),
        'smtp-password': String(default=''),
        # Logging
        'log-level': String(default='warning'),
        'log-email': Email(default=''),
        # Time events
        'cron-interval': Integer(default=60),
        # Security
        'session-timeout': ExpireValue(default=timedelta(0)),
        # Tuning
        'database-size': String(default='19500:20500'),
        'database-readonly': Boolean(default=False),
        'index-text': Boolean(default=True),
        'max-width': Integer(default=None),
        'max-height': Integer(default=None),
        'accept-cors': Integer(default=1),
        'wsgi_application': String(default="ikaaro.web.wsgi"),
    }


def get_config(target):
    return ServerConfig(f'{target}/config.conf')
