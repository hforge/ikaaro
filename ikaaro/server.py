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
from cProfile import runctx
from email.parser import HeaderParser
from json import loads
from io import BytesIO
from datetime import timedelta
from time import strftime
import inspect
import json
import pickle
from os import fdopen, getpgid, getpid, kill, mkdir, remove
from os.path import join
from psutil import pid_exists
import sys
from time import time
from traceback import format_exc
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from signal import SIGINT, SIGTERM
from requests import Request
from tempfile import mkstemp
from wsgiref.util import setup_testing_defaults

# Import from gevent
from gevent.pywsgi import WSGIServer, WSGIHandler
from gevent.signal import signal as gevent_signal

# Import from itools
from itools.core import become_daemon, vmsize
from itools.database import Metadata, RangeQuery
from itools.database import make_database, get_register_fields
from itools.datatypes import Boolean, Email, Integer, String, Tokens
from itools.fs import lfs
from itools.handlers import ConfigFile
from itools.log import Logger, register_logger
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL
from itools.log import log_error, log_warning, log_info
from itools.loop import cron
from itools.uri import get_reference, get_uri_path, Path
from itools.web import WebLogger
from itools.web import set_context, get_context
from itools.web.dispatcher import URIDispatcher
from itools.web.server import AccessLogger

# Import from ikaaro
from ikaaro.web.wsgi import application

# Import from ikaaro.web
from database import get_database
from datatypes import ExpireValue
from root import Root
from views import CachedStaticView
from skins import skin_registry
from views import IkaaroStaticView



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
cron-interval = 0

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
# To accept cross origin requests, set this option to 1 (default is 0)
#
accept-cors = 0

# The size of images can be controlled by setting the following values.
# (ie. max-width = 1280) (by default it is None, keeping original size).
#
max-width =
max-height =
""")





log_levels = {
    'debug': DEBUG,
    'info': INFO,
    'warning': WARNING,
    'error': ERROR,
    'fatal': FATAL}


def ask_confirmation(message, confirm=False):
    if confirm is True:
        print message + 'Y'
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
        exec('import %s' % name)



def get_pid(target):
    try:
        pid = open(target).read()
    except IOError:
        return None

    pid = int(pid)
    try:
        getpgid(pid)
    except OSError:
        return None
    return pid


def stop_server(target):
    msg = 'Stoping server...'
    log_info(msg)
    pid = get_pid('%s/pid' % target)
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
    modules = modules or []
    # Get modules
    for module in modules:
        exec('import %s' % module)
    # Load the root class
    if root is None:
        root_class = Root
    else:
        modules.insert(0, root)
        exec('import %s' % root)
        exec('root_class = %s.Root' % root)
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
    open('%s/config.conf' % target, 'w').write(config)

    # Create database
    database = make_database(target, size_min, size_max, backend=backend)
    database.close()
    database = get_database(target, size_min, size_max, backend=backend)

    # Create the folder structure
    mkdir('%s/log' % target)
    mkdir('%s/spool' % target)

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
    if the_server and get_server() != None:
        raise ValueError('Server is already defined')
    server = the_server


class ServerHandler(WSGIHandler):

    def format_request(self):
        now = strftime('%d/%b/%Y:%H:%M:%S %z')
        length = self.response_length or '-'
        if self.environ.get('REQUEST_TIME'):
            delta = '%.6f' % self.environ['REQUEST_TIME']
        else:
            delta = '-'
        client_address = self.environ.get('HTTP_X_FORWARDED_FOR')
        return '%s - - [%s] "%s" %s %s %s' % (
            client_address or '127.0.0.1',
            now,
            self.requestline or '',
            (self._orig_status or self.status or '000').split()[0],
            length,
            delta)


class Server(object):

    timestamp = None
    port = None
    environment = {}
    modules = []
    access_log = None
    event_log = None
    database = None
    session_timeout = timedelta(0)
    accept_cors = False
    dispatcher = URIDispatcher()
    wsgi_server = None
    cron_statistics = {}


    def __init__(self, target, read_only=False, cache_size=None,
                 profile_space=False, port=None):
        set_server(self)
        # Set target
        target = lfs.get_absolute_path(target)
        self.target = target
        # Read only ?
        self.read_only = read_only
        # Set timestamp
        self.timestamp = str(int(time() / 2))
        # Load the config
        config = self.load_config()
        # Load modules
        load_modules(config)
        self.modules = config.get_value('modules')
        # Find out the port to listen
        if port:
            self.port = int(port)
        else:
            self.port = self.config.get_value('listen-port')
        # Contact Email
        self.smtp_from = config.get_value('smtp-from')

        # Full-text indexing
        self.index_text =  config.get_value('index-text', type=Boolean,
                                            default=True)
        # Accept cors
        self.accept_cors = config.get_value(
            'accept-cors', type=Boolean, default=False)

        # Profile Memory
        if profile_space is True:
            import guppy.heapy.RM

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
            with open(environement_path, 'r') as f:
                data = f.read()
                self.environment = json.loads(data)
        # Access log
        path = '%s/log/access' % target
        self.access_log = AccessLogger(path, rotate=timedelta(weeks=3))
        register_logger(self.access_log, 'itools.web_access')
        # Events log
        event_log = '%s/log/events' % target
        logger = WebLogger(event_log)
        register_logger(logger, 'itools.web')
        # Useful the current uploads stats
        self.upload_stats = {}

        # Email service
        self.spool = lfs.resolve2(self.target, 'spool')
        spool_failed = '%s/failed' % self.spool
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
        log_file = '%s/log/events' % target
        log_level = config.get_value('log-level')
        if log_level not in log_levels:
            msg = 'configuraion error, unexpected "%s" value for log-level'
            raise ValueError(msg % log_level)
        log_level = log_levels[log_level]
        logger = Logger(log_file, log_level, rotate=timedelta(weeks=3))
        register_logger(logger, None)
        # Logging access
        logger = WebLogger(log_file, log_level)
        register_logger(logger, 'itools.web')
        # Logging cron
        log_file = '%s/log/cron' % target
        logger = Logger(log_file, rotate=timedelta(weeks=3))
        register_logger(logger, 'itools.cron')
        # Session timeout
        self.session_timeout = get_value('session-timeout')
        # Register routes
        self.register_dispatch_routes()


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

    #def log_access(self, host, request_line, status_code, body_length):
    #    if host:
    #        host = host.split(',', 1)[0].strip()
    #    now = strftime('%d/%b/%Y:%H:%M:%S %z')
    #    message = '%s - - [%s] "%s" %d %d %.3f\n' % (host, now, request_line,
    #                                                 status_code, body_length,
    #                                                 self.request_time)
    #    log_info(message, domain='itools.web_access')


    def get_database(self):
        database = self.database
        # Reopen so if we have one readonly request it will works
        database.backend.catalog._db.reopen()
        # Ok
        return database


    def check_consistency(self, quick):
        log_info('Check database consistency')
        # Check the server is not running
        if self.read_only:
            pid = get_pid('%s/pid_ro' % self.target)
        else:
            pid = get_pid('%s/pid' % self.target)
        if pid is not None:
            msg = '[%s] The Web Server is already running.' % self.target
            log_warning(msg)
            print(msg)
            return False
        # Ok
        return True


    def start(self, detach=False, profile=False, loop=True):
        msg = 'Start database %s %s %s' % (detach, profile, loop)
        log_info(msg)
        self.profile = '{0}/log/profile'.format(self.target) if profile else None
        # Daemon mode
        if detach:
            become_daemon()

        # Find out the IP to listen to
        address = self.config.get_value('listen-address').strip()
        if not address:
            raise ValueError, 'listen-address is missing from config.conf'
        # Check port
        if self.port is None:
            raise ValueError('listen-port is missing from config.conf')

        # Save PID
        pid = getpid()
        with open(self.target + '/pid', 'w') as f:
            f.write(str(pid))
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
        from itools.database.backends.catalog import make_catalog
        msg = 'reindex catalog %s %s %s' % (quiet, quick, as_test)
        log_info(msg)
        if self.is_running_in_rw_mode():
            print 'Cannot proceed, the server is running in read-write mode.'
            return
        # Create a temporary new catalog
        catalog_path = '%s/catalog.new' % self.target
        if lfs.exists(catalog_path):
            lfs.remove(catalog_path)
        catalog = make_catalog(catalog_path, get_register_fields())
        # Get the root
        root = self.root
        # Update
        t0, v0 = time(), vmsize()
        doc_n = 0
        error_detected = False
        if as_test:
            log = open('%s/log/update-catalog' % self.target, 'w').write
        with self.database.init_context() as context:
            for obj in root.traverse_resources():
                if not quiet or doc_n % 10000==0:
                    print('{0} {1}'.format(doc_n, obj.abspath))
                doc_n += 1
                context.resource = obj
                values = obj.get_catalog_values()
                # Index the document
                try:
                    catalog.index_document(values)
                except Exception:
                    if as_test:
                        error_detected = True
                        log('*** Error detected ***\n')
                        log('Abspath of the resource: %r\n\n' % str(obj.abspath))
                        log(format_exc())
                        log('\n')
                    else:
                        raise
                # Free Memory
                del obj
                self.database.make_room()

        if not error_detected:
            if as_test:
                # Delete the empty log file
                remove('%s/log/update-catalog' % self.target)

            # Update / Report
            t1, v1 = time(), vmsize()
            v = (v1 - v0)/1024
            print '[Update] Time: %.02f seconds. Memory: %s Kb' % (t1 - t0, v)
            # Commit
            print '[Commit]',
            sys.stdout.flush()
            catalog.save_changes()
            catalog.close()
            # Commit / Replace
            old_catalog_path = '%s/catalog' % self.target
            if lfs.exists(old_catalog_path):
                lfs.remove(old_catalog_path)
            lfs.move(catalog_path, old_catalog_path)
            # Commit / Report
            t2, v2 = time(), vmsize()
            v = (v2 - v1)/1024
            print 'Time: %.02f seconds. Memory: %s Kb' % (t2 - t1, v)
            return True
        else:
            print '[Update] Error(s) detected, the new catalog was NOT saved'
            print ('[Update] You can find more infos in %r' %
                   join(self.target, 'log/update-catalog'))
            return False


    def get_pid(self):
        return get_pid('%s/pid' % self.target)


    def is_running(self):
        pid = self.get_pid()
        return pid_exists(pid)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        set_server(None)


    def close(self):
        log_info('Close server')
        self.database.close()


    def stop(self, force=False):
        msg = 'Stoping server...'
        log_info(msg)
        print(msg)
        # Stop wsgi server
        if self.wsgi_server:
            self.wsgi_server.stop()
        # Close database
        self.close()


    def stop_signal(self, signal, handler):
        self.stop()


    def listen(self, address, port):
        # Say hello
        msg = 'Listing at port %s' % port
        log_info(msg)
        self.port = port
        # Say hello
        msg = 'Listen %s:%d' % (address, port)
        print(msg)
        # Serve
        log_info(msg)
        if address == '*':
            address = ''
        self.port = port
        self.wsgi_server = WSGIServer(
            (address or '', port), application,
            handler_class=ServerHandler,
            log=self.access_log)
        gevent_signal(SIGTERM, self.stop_signal)
        gevent_signal(SIGINT, self.stop_signal)
        if self.profile:
            runctx("self.wsgi_server.serve_forever()", globals(), locals(), self.profile)
        else:
            self.wsgi_server.serve_forever()


    #def save_running_informations(self):
    #    # Save server running informations
    #    kw = {'pid': getpid(),
    #          'target': self.target,
    #          'read_only': self.read_only}
    #    data = pickle.dumps(kw)
    #    with open(self.target + '/running', 'w') as output_file:
    #        output_file.write(data)


    #def get_running_informations(self):
    #    try:
    #        with open(self.target + '/running', 'r') as output_file:
    #            data = output_file.read()
    #            return pickle.loads(data)
    #    except IOError:
    #        return None


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
            raise ValueError, '"smtp-host" is not set in config.conf'

        spool = lfs.resolve2(self.target, 'spool')
        tmp_file, tmp_path = mkstemp(dir=spool)
        file = fdopen(tmp_file, 'w')
        try:
            file.write(message.as_string())
        finally:
            file.close()


    def flush_spool(self):
        cron(self._smtp_send, timedelta(seconds=1))


    def send_email(self, message):
        self.save_email(message)
        self.flush_spool()


    def _smtp_send(self):
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
                spool.move(name, 'failed/%s' % name)
                return 60 if get_names() else False
            log_info('CONNECTED to %s' % smtp_host)

            # 2. Login
            if self.smtp_login and self.smtp_password:
                smtp.login(self.smtp_login, self.smtp_password)

            # 3. Send message
            try:
                message = spool.open(name).read()
                headers = HeaderParser().parsestr(message)
                subject = headers['subject']
                from_addr = headers['from']
                to_addr = headers['to']
                smtp.sendmail(from_addr, to_addr, message)
                # Remove
                spool.remove(name)
                # Log
                log_msg = 'Email "%s" sent from "%s" to "%s"'
                log_info(log_msg % (subject, from_addr, to_addr))
            except SMTPRecipientsRefused:
                # The recipient addresses has been refused
                self.smtp_log_error()
                spool.move(name, 'failed/%s' % name)
            except SMTPResponseException, excp:
                # The SMTP server returns an error code
                self.smtp_log_error()
                spool.move(name, 'failed/%s_%s' % (excp.smtp_code, name))
            except Exception:
                self.smtp_log_error()

            # 4. Close connection
            smtp.quit()

        # Is there something left?
        return 60 if get_names() else False


    def smtp_log_error(self):
        summary = 'Error sending email\n'
        details = format_exc()
        log_error(summary + details)


    def register_dispatch_routes(self):
        # Dispatch base routes from ikaaro
        self.register_urlpatterns_from_package('ikaaro.urls')
        for module in reversed(self.modules):
            self.register_urlpatterns_from_package('{}.urls'.format(module))
        # UI routes for skin
        ts = self.timestamp
        for name in skin_registry:
            skin = skin_registry[name]
            mount_path = '/ui/%s' % name
            skin_key = skin.get_environment_key(self)
            view = IkaaroStaticView(local_path=skin_key, mount_path=mount_path)
            self.dispatcher.add('/ui/%s/{name:any}' % name, view)
            mount_path = '/ui/cached/%s/%s' % (ts, name)
            view = CachedStaticView(local_path=skin_key, mount_path=mount_path)
            self.dispatcher.add('/ui/cached/%s/%s/{name:any}' % (ts, name), view)


    def register_urlpatterns_from_package(self, package):
        urlpatterns = None
        try:
            exec('from {} import urlpatterns'.format(package))
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
            context.git_message = u'[CRON]'
            # Go
            t0 = time()
            catalog = database.catalog
            query = RangeQuery('next_time_event', None, context.timestamp)
            search = database.search(query)
            if not search:
                return self.config.get_value('cron-interval')
            nb = len(search)
            msg = 'Cron launched for {nb} resources'.format(nb=nb)
            log_info(msg, domain='itools.cron')
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
                    log_error('Cron error\n' + format_exc())
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
                msg = 'Done for %s in %s seconds' % (brain.abspath, tcron1-tcron0)
                log_info(msg, domain='itools.cron')
            # Save changes
            if not error:
                try:
                    catalog.save_changes()
                    database.save_changes()
                except Exception:
                    log_error('Cron error on save changes\n' + format_exc())
                    context.root.alert_on_internal_server_error(context)
            # Log into cron.log
            t1 = time()
            if not error:
                msg = '[OK] Cron finished for {nb} resources in {s} seconds'.format(nb=nb, s=t1-t0)
            else:
                msg = '[ERROR] Cron finished for {nb} resources in {s} seconds'.format(nb=nb, s=t1-t0)
            log_info(msg, domain='itools.cron')
            # Log into access.log
            now = strftime('%d/%b/%Y:%H:%M:%S %z')
            message = '127.0.0.1 - - [%s] "GET /cron HTTP/1.1" 200 1 %.3f\n'
            log_info(message % (now, t1-t0), domain='itools.web_access')
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
            context=None, as_json=False, as_multipart=False, files=None, user=None, cookies=None):
        """Experimental method to do a request on the server"""
        from itools.web.router import RequestMethod
        headers = []
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
                'http://localhost:8080{0}'.format(path),
                json=body,
            )
            prepped = req.prepare()
        elif as_multipart:
            req = Request(
                method,
                'http://localhost:8080{0}'.format(path),
                data=body,
                files=files
            )
            prepped = req.prepare()
        else:
            req = Request(
                method,
                'http://localhost:8080{0}'.format(path),
                data=body,
            )
            prepped = req.prepare()
        # Build headers
        headers = [(key.lower(), value) for key, value in prepped.headers.items()]
        headers.append(('User-Agent', 'Firefox'))
        for key, value in headers:
            environ['HTTP_%s' % key.upper().replace('-', '_')] = value
        # Set wsgi input body
        environ['wsgi.input'] = BytesIO(prepped.body)
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
        # Cookies
        if cookies:
            for key, value in cookies.items():
                context.set_cookie(key, value)
        # Do request
        RequestMethod.handle_request(context)
        # Transform result
        if context.entity is None:
            response = None
        elif as_json and not str(context.status).startswith('3'):
            # Do not load json if 302 (url redirection)
            try:
                response = loads(context.entity)
            except ValueError:
                msg = 'Cannot load json {0}'.format(context.entity)
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
        'cron-interval': Integer(default=0),
        # Security
        'session-timeout': ExpireValue(default=timedelta(0)),
        # Tuning
        'database-size': String(default='19500:20500'),
        'database-readonly': Boolean(default=False),
        'index-text': Boolean(default=True),
        'max-width': Integer(default=None),
        'max-height': Integer(default=None),
    }


def get_config(target):
    return ServerConfig('{0}/config.conf'.format(target))
