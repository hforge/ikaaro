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
from datetime import timedelta
from email.parser import HeaderParser
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
from socket import gaierror
from tempfile import mkstemp

# Import from pygobject
from glib import GError

# Import from itools
from itools.core import become_daemon, get_abspath, vmsize
from itools.database import Metadata, RangeQuery
from itools.database import make_catalog, Resource, get_register_fields
from itools.database import check_database
from itools.datatypes import Boolean, Email, Integer, String, Tokens
from itools.fs import vfs, lfs
from itools.handlers import ConfigFile, ro_database
from itools.log import Logger, register_logger
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL
from itools.log import log_error, log_warning, log_info
from itools.loop import Loop, cron
from itools.web import WebServer, WebLogger
from itools.web import set_context, get_context
from itools.web import SoupMessage
from itools.web.static import StaticView

# Import from ikaaro
from context import CMSContext
from database import get_database, make_database
from datatypes import ExpireValue
from root import Root
from views import CachedStaticView
from update import is_instance_up_to_date
from urls import urlpatterns
from skins import skin_registry



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
listen-address = 127.0.0.1
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
database-size = 19500:20500
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



def get_root(database):
    metadata = database.get_handler('.metadata', cls=Metadata)
    cls = database.get_resource_class(metadata.format)
    return cls(metadata)


def get_fake_context(database, context_cls=CMSContext):
    context = context_cls()
    context.soup_message = SoupMessage()
    context.path = '/'
    context.database = database
    set_context(context)
    return context


def create_server(target, email, password, root,  modules,
                  listen_port='8080', smtp_host='localhost', log_email=None):
    # Get modules
    for module in modules:
        modules.append(module)
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
        smtp_host=smtp_host or 'localhost',
        smtp_from=email,
        log_email=log_email)
    open('%s/config.conf' % target, 'w').write(config)

    # Create the folder structure
    database = make_database(target)
    mkdir('%s/log' % target)
    mkdir('%s/spool' % target)

    # Create a fake context
    context = get_fake_context(database)
    context.set_mtime = True

    # Make the root
    metadata = Metadata(cls=root_class)
    database.set_handler('.metadata', metadata)
    root = root_class(metadata)
    # Re-init context with context cls
    context = get_fake_context(context.database, root.context_cls)
    context.set_mtime = True
    # Init root resource
    root.init_resource(email, password)
    # Set mtime
    root.set_property('mtime', context.timestamp)
    context.root = root
    # Save changes
    context.git_message = 'Initial commit'
    database.save_changes()
    # Index the root
    catalog = database.catalog
    catalog.save_changes()
    # Bravo!
    print('*')
    print('* Welcome to ikaaro')
    print('* A user with administration rights has been created for you:')
    print('*   username: %s' % email)
    print('*   password: %s' % password)
    print('*')
    print('* To start the new instance type:')
    print('*   icms-start.py %s' % target)
    print('*')


class ServerLoop(Loop):

    server = None

    def __init__(self, target, server, profile=None):
        self.server = server
        # Init
        pid_file = target + '/pid'
        proxy = super(ServerLoop, self)
        proxy.__init__(pid_file, profile)


    def run(self):
        # Save running informations
        self.server.save_running_informations()
        # Run
        proxy = super(ServerLoop, self)
        proxy.run()



class Server(WebServer):

    timestamp = None

    def __init__(self, target, read_only=False, cache_size=None,
                 profile_space=False):
        target = lfs.get_absolute_path(target)
        self.target = target
        self.read_only = read_only
        # Set timestamp
        self.timestamp = str(int(time() / 2))
        # Load the config
        config = get_config(target)
        self.config = config
        load_modules(config)

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
        database = get_database(target, size_min, size_max, read_only)
        self.database = database

        # Find out the root class
        root = get_root(database)

        # Init fake context
        context = get_fake_context(database, root.context_cls)
        context.server = self

        # Initialize
        access_log = '%s/log/access' % target
        super(Server, self).__init__(root, access_log=access_log)

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

        # Logging
        log_file = '%s/log/events' % target
        log_level = config.get_value('log-level')
        if log_level not in log_levels:
            msg = 'configuraion error, unexpected "%s" value for log-level'
            raise ValueError, msg % log_level
        log_level = log_levels[log_level]
        logger = Logger(log_file, log_level, rotate=timedelta(weeks=3))
        register_logger(logger, None)
        logger = WebLogger(log_file, log_level)
        register_logger(logger, 'itools.web')

        # Session timeout
        self.session_timeout = get_value('session-timeout')


    def check_consistency(self, quick):
        # Check the server is not running
        pid = get_pid('%s/pid' % self.target)
        if pid is not None:
            print '[%s] The Web Server is already running.' % self.target
            return False

        # Check for database consistency
        if quick is False and check_database(self.target) is False:
            return False

        # Check instance is up to date
        if not is_instance_up_to_date(self.target):
            print 'The instance is not up-to-date, please type:'
            print
            print '    $ icms-update.py %s' % self.target
            print
            return False
        return True


    def start(self, detach=False, profile=False, loop=True):
        self.loop = ServerLoop(
              target=self.target,
              server=self,
              profile=profile)
        # Daemon mode
        if detach:
            become_daemon()

        # Update Git tree-cache, to speed things up
        self.database.worktree.update_tree_cache()

        # Find out the IP to listen to
        address = self.config.get_value('listen-address').strip()
        if not address:
            raise ValueError, 'listen-address is missing from config.conf'
        if address == '*':
            address = None

        # Find out the port to listen
        port = self.config.get_value('listen-port')
        if port is None:
            raise ValueError, 'listen-port is missing from config.conf'

        # Listen & set context
        root = self.root
        self.listen(address, port)

        # Call method on root at start
        context = get_context()
        root.launch_at_start(context)

        # Set cron interval
        interval = self.config.get_value('cron-interval')
        if interval:
            cron(self.cron_manager, interval)

        # Run
        profile = ('%s/log/profile' % self.target) if profile else None
        # Init loop
        if loop:
            try:
                self.loop.run()
            except KeyboardInterrupt:
                self.close()
        # Ok
        return True


    def reindex_catalog(self, quiet=False, quick=False, as_test=False):
        if self.is_running_in_rw_mode():
            print 'Cannot proceed, the server is running in read-write mode.'
            return
        # Check for database consistency
        if quick is False and check_database(self.target) is False:
            return False
        # Create a temporary new catalog
        catalog_path = '%s/catalog.new' % self.target
        if lfs.exists(catalog_path):
            lfs.remove(catalog_path)
        catalog = make_catalog(catalog_path, get_register_fields())

        # Get the root
        root = self.root

        # Build a fake context
        context = self.get_fake_context()

        # Update
        t0, v0 = time(), vmsize()
        doc_n = 0
        error_detected = False
        if as_test:
            log = open('%s/log/update-catalog' % self.target, 'w').write
        for obj in root.traverse_resources():
            if not isinstance(obj, Resource):
                continue
            if not quiet:
                print doc_n, obj.abspath
            doc_n += 1
            context.resource = obj

            # Index the document
            try:
                catalog.index_document(obj)
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


    def stop(self, force=False):
        proxy = super(Server, self)
        proxy.stop()
        print 'Stoping server...'
        self.kill(force)


    def kill(self, force=False):
        pid = get_pid('%s/pid' % self.target)
        if pid is None:
            print '[%s] Web Server not running.' % self.target
        else:
            signal = SIGTERM if force else SIGINT
            kill(pid, signal)
            if force:
                print '[%s] Web Server shutting down...' % self.target
            else:
                print '[%s] Web Server shutting down (gracefully)...' % self.target


    def listen(self, address, port):
        super(Server, self).listen(address, port)
        # Register routes
        self.register_dispatch_routes()



    def save_running_informations(self):
        # Save server running informations
        kw = {'pid': getpid(),
              'target': self.target,
              'read_only': self.read_only}
        data = pickle.dumps(kw)
        with open(self.target + '/running', 'w') as output_file:
            output_file.write(data)


    def get_running_informations(self):
        try:
            with open(self.target + '/running', 'r') as output_file:
                data = output_file.read()
                return pickle.loads(data)
        except IOError:
            return None


    def is_running_in_rw_mode(self, mode='running'):
        is_running = self.is_running()
        if not is_running:
            return False
        if mode == 'request':
            address = self.config.get_value('listen-address').strip()
            if address == '*':
                address = '127.0.0.1'
            port = self.config.get_value('listen-port')

            url = 'http://%s:%s/;_ctrl' % (address, port)
            try:
                h = vfs.open(url)
            except GError:
                # The server is not running
                return False
            data = h.read()
            return json.loads(data)['read-only'] is False
        elif mode == 'running':
            kw = self.get_running_informations()
            return not kw.get('read_only', False)


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
            except gaierror, excp:
                log_warning('%s: "%s"' % (excp[1], smtp_host))
                return 60 # 1 minute
            except Exception:
                self.smtp_log_error()
                return 60 # 1 minute
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
        # Dispatch routes
        for urlpattern_object in urlpatterns:
            for pattern, view in urlpattern_object.get_patterns():
                self.dispatcher.add(pattern, view)
        # UI routes for skin
        for name in skin_registry:
            skin = skin_registry[name]
            mount_path = '/ui/%s' % name
            view = StaticView(local_path=skin.key, mount_path=mount_path)
            self.dispatcher.add('/ui/%s/{name:any}' % name, view)
            mount_path = '/ui/cached/%s' % name
            view = CachedStaticView(local_path=skin.key, mount_path=mount_path)
            self.dispatcher.add('/ui/cached/%s/{name:any}' % name, view)
        # UI routes for /ui/*.js /ui/*.css (should be OBSOLETE)
        view = StaticView(local_path=get_abspath('ui/'), mount_path='/ui')
        self.dispatcher.add('/ui/{name:any}', view)


    #######################################################################
    # Time events
    #######################################################################
    def cron_manager(self):
        database = self.database

        # Build fake context
        context = get_fake_context(database, self.root.context_cls)
        context.server = self
        context.init_context()
        context.is_cron = True

        # Go
        query = RangeQuery('next_time_event', None, context.timestamp)
        for brain in database.search(query).get_documents():
            payload = pickle.loads(brain.next_time_event_payload)
            resource = database.get_resource(brain.abspath)
            try:
                resource.time_event(payload)
            except Exception:
                # Log error
                log_error('Cron error\n' + format_exc())
                context.root.alert_on_internal_server_error(context)
            # Reindex resource without committing
            catalog = database.catalog
            catalog.unindex_document(str(resource.abspath))
            catalog.index_document(resource.get_catalog_values())
            catalog.save_changes()

        # Save changes
        database.save_changes()

        # Again, and again
        return self.config.get_value('cron-interval')



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
    return ro_database.get_handler('%s/config.conf' % target, ServerConfig)
