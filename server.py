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
from traceback import format_exc

# Import from pygobject
from gobject import idle_add, timeout_add_seconds

# Import from xapian
from xapian import DatabaseOpeningError

# Import from itools
from itools.datatypes import Boolean
from itools.http import Request
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL, log_error
from itools.uri import get_reference, get_host_from_authority
from itools import vfs
from itools.vfs import cwd
from itools.web import WebServer, Context, set_context

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
    request = Request()
    context = Context(request)
    set_context(context)
    return context


class Server(WebServer):

    def __init__(self, target, address=None, port=None, read_only=False,
                 cache_size=None):
        target = cwd.get_uri(target)
        self.target = get_reference(target)
        path = self.target.path

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

        # Logs
        event_log = '%s/log/events' % path
        access_log = '%s/log/access' % path
        log_level = config.get_value('log-level')
        try:
            log_level = log_levels[log_level]
        except KeyError:
            msg = 'configuraion error, unexpected "%s" value for log-level'
            raise ValueError, msg % log_level

        # Profile CPU
        profile = config.get_value('profile-time')
        if profile is True:
            self.profile_path = '%s/log/profile' % path
        else:
            self.profile_path = None
        # Profile Memory
        if config.get_value('profile-space') is True:
            import guppy.heapy.RM

        # The database
        if cache_size is None:
            cache_size = config.get_value('database-size')
        database = get_database(path, cache_size, read_only=read_only)
        self.database = database

        # Find out the root class
        root = get_root(database, target)

        # Initialize
        WebServer.__init__(self, root, address=address, port=port,
                           access_log=access_log, event_log=event_log,
                           log_level=log_level, pid_file='%s/pid' % path)

        # Initialize the spool
        spool = self.target.resolve_name('spool')
        spool = str(spool)
        self.spool = vfs.open(spool)

        # The SMTP host
        get_value = get_config(self.target).get_value
        self.smtp_host = get_value('smtp-host')
        self.smtp_login = get_value('smtp-login', default='').strip()
        self.smtp_password = get_value('smtp-password', default='').strip()

        # The logs
        self.smtp_activity_log_path = '%s/log/spool' % self.target.path
        self.smtp_activity_log = open(self.smtp_activity_log_path, 'a+')
        idle_add(self.smtp_send_idle_callback)


    #######################################################################
    # Email
    #######################################################################
    def send_email(self, message):
        # Check the SMTP host is defined
        config = get_config(self.target)
        if not config.get_value('smtp-host'):
            raise ValueError, '"smtp-host" is not set in config.conf'

        spool = self.target.resolve_name('spool')
        spool = str(spool.path)
        tmp_file, tmp_path = mkstemp(dir=spool)
        file = fdopen(tmp_file, 'w')
        try:
            file.write(message.as_string())
        finally:
            file.close()

        idle_add(self.smtp_send_idle_callback)


    def _smtp_send(self):
        spool = self.spool
        smtp_host = self.smtp_host
        log = self.smtp_log_activity

        # Find out emails to send
        locks = set()
        names = set()
        for name in spool.get_names():
            if name[-5:] == '.lock':
                locks.add(name[:-5])
            else:
                names.add(name)
        names.difference_update(locks)
        # Is there something to send?
        if len(names) == 0:
            return 0

        # Open connection
        try:
            smtp = SMTP(smtp_host)
            if self.smtp_login and self.smtp_password:
                smtp.login(self.smtp_login, self.smtp_password)
        except gaierror, excp:
            log('%s: "%s"' % (excp[1], smtp_host))
            return 1
        except:
            self.smtp_log_error()
            return 1

        # Send emails
        error = 0
        for name in names:
            try:
                # Send message
                message = spool.open(name).read()
                headers = HeaderParser().parsestr(message)
                subject = headers['subject']
                from_addr = headers['from']
                to_addr = headers['to']
                # Send message
                smtp.sendmail(from_addr, to_addr, message)
                # Remove
                spool.remove(name)
                # Log
                log('SENT "%s" from "%s" to "%s"' % (subject, from_addr,
                    to_addr))
            except (SMTPRecipientsRefused, SMTPResponseException):
                # the SMTP server returns an error code
                # or the recipient addresses has been refused
                # Log
                self.smtp_log_error()
                # Remove
                spool.remove(name)
                error = 1
            except Exception:
                # Other error ...
                self.smtp_log_error()
                error = 1

        # Close connection
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


    def smtp_log_activity(self, msg):
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
        summary = 'Error sending email\n'
        details = format_exc()
        log_error(summary + details)


    #######################################################################
    # Web
    #######################################################################
    def get_pid(self):
        return get_pid(self.target.path)


    def init_context(self, context):
        WebServer.init_context(self, context)
        context.database = self.database
        context.message = None


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

