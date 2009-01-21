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
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
from os import fdopen
import sys
from tempfile import mkstemp

# Import from xapian
from xapian import DatabaseOpeningError

# Import from itools
from itools.datatypes import Boolean, Integer, String, Tokens
from itools.handlers import ConfigFile
from itools.uri import get_absolute_reference2
from itools import vfs
from itools.web import Server as BaseServer

# Import from ikaaro
from database import get_database
from metadata import Metadata
from registry import get_resource_class
from utils import is_pid_running
from website import WebSite



class ServerConfig(ConfigFile):

    schema = {
        'modules': Tokens(default=()),
        'listen-address': String(default=''),
        'listen-port': Integer(default=8080),
        'log-level': String(default='warning'),
        'smtp-host': String(default=''),
        'smtp-from': String(default=''),
        'smtp-login': String(default=''),
        'smtp-password': String(default=''),
        'profile': Boolean(default=False),
    }


log_levels = {
    'debug': DEBUG,
    'info': INFO,
    'warning': WARNING,
    'error': ERROR,
    'critical': CRITICAL}


def ask_confirmation(message, confirm=False):
    if confirm is True:
        print message + 'Y'
        return True

    sys.stdout.write(message)
    sys.stdout.flush()
    line = sys.stdin.readline()
    line = line.strip().lower()
    return line == 'y'



def get_config(target):
    return ServerConfig('%s/config.conf' % target)



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



class Server(BaseServer):

    def __init__(self, target, address=None, port=None, read_only=False):
        target = get_absolute_reference2(target)
        self.target = target
        path = target.path

        # Load the config
        config = get_config(target)
        load_modules(config)

        # Find out the IP to listen to
        if not address:
            address = config.get_value('listen-address').strip()

        # Find out the port to listen
        if not port:
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

        # Profile
        profile = config.get_value('profile')
        if profile is True:
            profile_path = '%s/log/profile' % path
            if not vfs.exists(profile_path):
                vfs.make_folder(profile_path)
        else:
            profile_path = None

        # The database
        database = get_database(path, read_only=read_only)
        self.database = database

        # Find out the root class
        root = get_root(database, target)

        # Initialize
        BaseServer.__init__(self, root, address=address, port=port,
                            access_log=access_log, event_log=event_log,
                            log_level=log_level, pid_file='%s/pid' % path,
                            profile_path=profile_path)


    #######################################################################
    # API / Private
    #######################################################################
    def get_pid(self):
        return get_pid(self.target.path)


    def send_email(self, message):
        # Check the SMTP host is defined
        config = get_config(self.target)
        if not config.get_value('smtp-host'):
            raise ValueError, '"smtp-host" is not set in config.conf'

        spool = self.target.resolve2('spool')
        spool = str(spool.path)
        tmp_file, tmp_path = mkstemp(dir=spool)
        file = fdopen(tmp_file, 'w')
        try:
            file.write(message.as_string())
        finally:
            file.close()


    #######################################################################
    # API / Public
    #######################################################################
    def init_context(self, context):
        BaseServer.init_context(self, context)
        context.database = self.database
        # Set the list of needed resources. The method we are going to
        # call may need external resources to be rendered properly, for
        # example it could need an style sheet or a javascript file to
        # be included in the html head (which it can not control). This
        # attribute lets the interface to add those resources.
        context.styles = []
        context.scripts = []
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
        hostname = uri.authority.host

        # Check first the root
        if hostname in root.get_property('vhosts'):
            return

        # Check the sub-sites
        for site in root.search_resources(cls=WebSite):
            if hostname in site.get_property('vhosts'):
                context.site_root = site
                return


    # FIXME Short-cut, to be removed
    def change_resource(self, resource):
        self.database.change_resource(resource)
