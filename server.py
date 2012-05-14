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
from os import fdopen, getpgid
from smtplib import SMTP, SMTPRecipientsRefused, SMTPResponseException
from socket import gaierror
import sys
from tempfile import mkstemp
from traceback import format_exc

# Import from pygobject
from glib import GError

# Import from itools
from itools.core import get_abspath
from itools.database import Metadata, RangeQuery
from itools.datatypes import Boolean, Email, Integer, String, Tokens
from itools.fs import vfs, lfs
from itools.handlers import ConfigFile, ro_database
from itools.log import Logger, register_logger
from itools.log import DEBUG, INFO, WARNING, ERROR, FATAL
from itools.log import log_error, log_warning, log_info
from itools.loop import cron
from itools.web import WebServer, WebLogger
from itools.web import StaticContext, set_context
from itools.web import SoupMessage

# Import from ikaaro
from context import CMSContext
from database import get_database
from datatypes import ExpireValue
from skins import skin_registry


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


def get_fake_context(database):
    context = CMSContext()
    context.soup_message = SoupMessage()
    context.path = '/'
    context.database = database
    set_context(context)
    return context



class Server(WebServer):

    def __init__(self, target, read_only=False, cache_size=None,
                 profile_space=False):
        target = lfs.get_absolute_path(target)
        self.target = target

        # Load the config
        config = get_config(target)
        self.config = config
        load_modules(config)

        # Contact Email
        self.smtp_from = config.get_value('smtp-from')

        # Full-text indexing
        self.index_text =  config.get_value('index-text', type=Boolean,
                                            default=True)

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


    def get_pid(self):
        return get_pid('%s/pid' % self.target)


    def set_context(self, path, context):
        context = super(Server, self).set_context(path, context)
        context.database = self.database


    def listen(self, address, port):
        super(Server, self).listen(address, port)
        # Set ui
        context = StaticContext(local_path=get_abspath('ui'))
        self.set_context('/ui', context)
        for name in skin_registry:
            skin = skin_registry[name]
            context = StaticContext(local_path=skin.key)
            self.set_context('/ui/%s' % name, context)


    def is_running_in_rw_mode(self):
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


    #######################################################################
    # Time events
    #######################################################################
    def cron_manager(self):
        database = self.database

        # Build fake context
        context = get_fake_context(database)
        context.server = self
        context.init_context()

        # Go
        query = RangeQuery('next_time_event', None, context.timestamp)
        for brain in database.search(query).get_documents():
            payload = pickle.loads(brain.next_time_event_payload)
            resource = database.get_resource(brain.abspath)
            resource.time_event(payload)
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
