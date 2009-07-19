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
from datetime import datetime
from email.parser import HeaderParser
from os import fdopen, fstat
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from socket import gaierror
import sys
from tempfile import mkstemp
from traceback import print_exc

# Import from pygobject
from gobject import idle_add, timeout_add_seconds

# Import from pygobject
from glib import GError

# Import from xapian
from xapian import DatabaseOpeningError

# Import from itools
from itools.datatypes import Boolean
from itools.fs import vfs, lfs
from itools.log import Logger, register_logger
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL
from itools.soup import SoupMessage
from itools.uri import get_host_from_authority
from itools.web import WebServer, WebLogger, Context, set_context

# Import from ikaaro
from config import get_config
from database import get_database
from metadata import Metadata
from registry import get_resource_class
from utils import is_pid_running
from website import WebSite


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
        pid = open('%s/pid' % target).read()
    except IOError:
        return None

    pid = int(pid)
    if is_pid_running(pid):
        return pid
    return None



def get_root(database, target):
    path = '%s/database/.metadata' % target
    metadata = database.get_handler(path, cls=Metadata)
    cls = get_resource_class(metadata.format)
    # Build the root resource
    root = cls(metadata)
    # FIXME Should be None
    root.name = root.class_title.message.encode('utf_8')
    return root


def get_fake_context():
    soup_message = SoupMessage()
    context = Context(soup_message, '/')
    set_context(context)
    return context


class Server(WebServer):

    def __init__(self, target, address=None, port=None, read_only=False,
                 cache_size=None):
        target = lfs.get_absolute_path(target)
        self.target = target

        # Load the config
        config = get_config(target)
        load_modules(config)

        # Find out the IP to listen to
        if address is None:
            address = config.get_value('listen-address').strip()

        # Find out the port to listen
        if port is None:
            port = config.get_value('listen-port')

        # Contact Email
        self.smtp_from = config.get_value('smtp-from')

        # Full-text indexing
        self.index_text =  config.get_value('index-text', type=Boolean,
                                            default=True)

        # Profile CPU
        profile = config.get_value('profile-time')
        if profile is True:
            self.profile_path = '%s/log/profile' % target
        else:
            self.profile_path = None
        # Profile Memory
        if config.get_value('profile-space') is True:
            import guppy.heapy.RM

        # The database
        if cache_size is None:
            cache_size = config.get_value('database-size')
        if ':' in cache_size:
            size_min, size_max = cache_size.split(':')
        else:
            size_min = size_max = cache_size
        size_min, size_max = int(size_min), int(size_max)
        database = get_database(target, size_min, size_max,
                read_only=read_only)
        self.database = database

        # Find out the root class
        root = get_root(database, target)

        # Initialize
        access_log = '%s/log/access' % target
        WebServer.__init__(self, root, address=address, port=port,
                           access_log=access_log, pid_file='%s/pid' % target)

        # Initialize the spool
        spool = lfs.resolve2(self.target, 'spool')
        self.spool = lfs.open(spool)
        # spool/failed
        spool_failed = '%s/failed' % spool
        spool_failed = str(spool_failed)
        if not lfs.exists(spool_failed):
            lfs.make_folder(spool_failed)

        # The SMTP host
        get_value = get_config(target).get_value
        self.smtp_host = get_value('smtp-host')
        self.smtp_login = get_value('smtp-login', default='').strip()
        self.smtp_password = get_value('smtp-password', default='').strip()

        # The logs
        self.smtp_activity_log_path = '%s/log/spool' % target
        self.smtp_activity_log = open(self.smtp_activity_log_path, 'a+')
        self.smtp_error_log_path = '%s/log/spool_error' % target
        self.smtp_error_log = open(self.smtp_error_log_path, 'a+')

        # Logging
        log_file = '%s/log/events' % target
        log_level = config.get_value('log-level')
        if log_level not in log_levels:
            msg = 'configuraion error, unexpected "%s" value for log-level'
            raise ValueError, msg % log_level
        log_level = log_levels[log_level]
        logger = Logger(log_file, log_level)
        register_logger(logger, None)
        logger = WebLogger(log_file, log_level)
        register_logger(logger, 'itools.http', 'itools.web')


    #######################################################################
    # Email
    #######################################################################
    def send_email(self, message):
        # Check the SMTP host is defined
        config = get_config(self.target)
        if not config.get_value('smtp-host'):
            raise ValueError, '"smtp-host" is not set in config.conf'

        spool = lfs.resolve2(self.target, 'spool')
        tmp_file, tmp_path = mkstemp(dir=spool)
        file = fdopen(tmp_file, 'w')
        try:
            file.write(message.as_string())
        finally:
            file.close()

        idle_add(self.send_emails_callback)


    def _smtp_send(self):
        # Find out emails to send
        locks = set()
        names = set()
        for name in self.spool.get_names():
            if name == 'failed':
                # Skip "failed" special directory
                continue
            if name[-5:] == '.lock':
                locks.add(name[:-5])
            else:
                names.add(name)
        names.difference_update(locks)
        # Is there something to send?
        if len(names) == 0:
            return 0

        # Send emails
        for name in names:
            # 1. Open connection
            try:
                smtp = SMTP(self.smtp_host)
            except gaierror, excp:
                self.smtp_log_activity('%s: "%s"' % (excp[1], self.smtp_host))
                break
            except Exception:
                self.smtp_log_error()
                break
            self.smtp_log_activity('CONNECTED to %s' % self.smtp_host)

            # 2. Login
            if self.smtp_login and self.smtp_password:
                smtp.login(self.smtp_login, self.smtp_password)

            # 3. Send message
            try:
                message = self.spool.open(name).read()
                headers = HeaderParser().parsestr(message)
                subject = headers['subject']
                from_addr = headers['from']
                to_addr = headers['to']
                smtp.sendmail(from_addr, to_addr, message)
                # Remove
                self.spool.remove(name)
                # Log
                self.smtp_log_activity(
                    'SENT "%s" from "%s" to "%s"'
                    % (subject, from_addr, to_addr))
            except SMTPRecipientsRefused:
                # The recipient addresses has been refused
                self.smtp_log_error()
                self.spool.move(name, 'failed/%s' % name)
            except SMTPResponseException, excp:
                # The SMTP server returns an error code
                self.smtp_log_error()
                error_name = '%s_%s' % (excp.smtp_code, name)
                self.spool.move(name, 'failed/%s' % error_name)
            except Exception:
                self.smtp_log_error()

            # 4. Close connection
            smtp.quit()

        return error


    def smtp_send_idle_callback(self):
        # Error: try again later
        if self._smtp_send() == 1:
            timeout_add_seconds(60, self.smtp_send_time_callback)

        return False


    def smtp_send_time_callback(self):
        # Error: keep trying
        if self._smtp_send() == 1:
            return True

        return False


    def smpt_log_activity(self, msg):
        # The data to write
        data = '%s - %s\n' % (datetime.now(), msg)

        # Check the file has not been removed
        log = self.smtp_activity_log
        if fstat(log.fileno())[3] == 0:
            log = open(self.smtp_activity_log_path, 'a+')
            self.smtp_activity_log = log

        # Write
        log.write(data)
        log.flush()


    def smtp_log_error(self):
        # The data to write
        lines = [
            '\n',
            '%s\n' % ('*' * 78),
            'DATE: %s\n' % datetime.now(),
            '\n']
        data = ''.join(lines)

        # Check the file has not been removed
        log = self.smtp_error_log
        if fstat(log.fileno())[3] == 0:
            log = open(self.smtp_error_log_path, 'a+')
            self.smtp_error_log = log

        # Write
        log.write(data)
        print_exc(file=log) # FIXME Should be done before to reduce the risk
                            # of the log file being removed.
        log.flush()


    def is_running_in_rw_mode(self):
        url = 'http://localhost:%s/;_ctrl?name=read-only' % self.port
        try:
            h = vfs.open(url)
        except GError:
            # The server is not running
            return False

        return h.read() == 'no'


    #######################################################################
    # Web
    #######################################################################
    def get_pid(self):
        return get_pid(self.target)


    def init_context(self, context):
        WebServer.init_context(self, context)
        context.database = self.database
        context.message = None
        context.content_type = None


    def find_site_root(self, context):
        # Default to root
        root = self.root
        context.site_root = root

        # Check we have a URI
        uri = context.uri
        if uri is None:
            return

        # The site root depends on the host
        hostname = get_host_from_authority(uri.authority)

        results = self.database.catalog.search(vhosts=hostname)
        if len(results) == 0:
            return

        documents = results.get_documents()
        path = documents[0].abspath
        context.site_root = root.get_resource(path)


    # FIXME Short-cut, to be removed
    def change_resource(self, resource):
        self.database.change_resource(resource)


    def start(self):
        # Go
        if self.profile_path is not None:
            filename = self.profile_path
            runctx("WebServer.start(self)", globals(), locals(), filename)
        else:
            WebServer.start(self)

