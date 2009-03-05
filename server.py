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
from os import fdopen
import sys
from tempfile import mkstemp

# Import from xapian
from xapian import DatabaseOpeningError

# Import from itools
from itools.datatypes import Boolean, Integer, String, Tokens
from itools.handlers import ConfigFile, SafeDatabase
from itools.uri import get_absolute_reference2
from itools import vfs
from itools.web import Server as BaseServer
from itools.xapian import Catalog

# Import from ikaaro
from folder import Folder
from metadata import Metadata
from registry import get_resource_class
from utils import is_pid_running
from versioning import VersioningAware
from website import WebSite



class ServerConfig(ConfigFile):

    schema = {
        'modules': Tokens(default=()),
        'listen-address': String(default=''),
        'listen-port': Integer(default=8080),
        'smtp-host': String(default=''),
        'smtp-from': String(default=''),
        'smtp-login': String(default=''),
        'smtp-password': String(default=''),
        'debug': Boolean(default=False),
    }




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

    def __init__(self, target, address=None, port=None, debug=False,
                 read_only=False):
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
        debug = debug or config.get_value('debug')

        # The database
        if debug:
            database = SafeDatabase('%s/database.commit' % path, event_log)
        else:
            database = SafeDatabase('%s/database.commit' % path)
        self.database = database
        # The catalog
        # FIXME Backwards compatibility with 0.20
        try:
            self.catalog = Catalog('%s/catalog' % target, read_only=read_only)
        except DatabaseOpeningError, e:
            print e
            self.catalog = None

        # Find out the root class
        root = get_root(database, target)

        # Events
        self.resources_added = set()
        self.resources_changed = set()
        self.resources_removed = set()

        # Initialize
        BaseServer.__init__(self, root, address=address, port=port,
                            access_log=access_log, event_log=event_log,
                            debug=debug, pid_file='%s/pid' % path)


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


    def get_databases(self):
        return [self.database, self.catalog]


    def abort_transaction(self, context):
        # Clear events
        self.resources_removed.clear()
        self.resources_added.clear()
        self.resources_changed.clear()
        # Follow-up
        BaseServer.abort_transaction(self, context)


    def before_commit(self):
        root = self.root
        catalog = self.catalog
        # Removed
        for path in self.resources_removed:
            catalog.unindex_document(path)
        self.resources_removed.clear()

        # Added
        for path in self.resources_added:
            resource = root.get_resource(path)
            if isinstance(resource, VersioningAware):
                resource.commit_revision()
            catalog.index_document(resource)
        self.resources_added.clear()

        # Changed
        for path in self.resources_changed:
            resource = root.get_resource(path)
            if isinstance(resource, VersioningAware):
                resource.commit_revision()
            catalog.unindex_document(path)
            catalog.index_document(resource)
        self.resources_changed.clear()


    #######################################################################
    # API / Public
    #######################################################################
    def init_context(self, context):
        BaseServer.init_context(self, context)
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


    def remove_resource(self, resource):
        resources_removed = self.resources_removed
        resources_added = self.resources_added
        resources_changed = self.resources_changed

        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                if path in resources_added:
                    resources_added.remove(path)
                if path in resources_changed:
                    resources_changed.remove(path)
                resources_removed.add(path)
        else:
            path = str(resource.get_canonical_path())
            if path in resources_added:
                resources_added.remove(path)
            if path in resources_changed:
                resources_changed.remove(path)
            resources_removed.add(path)


    def add_resource(self, resource):
        if isinstance(resource, Folder):
            for x in resource.traverse_resources():
                path = str(x.get_canonical_path())
                self.resources_added.add(path)
        else:
            path = str(resource.get_canonical_path())
            self.resources_added.add(path)


    def change_resource(self, resource):
        path = str(resource.get_canonical_path())
        if path in self.resources_removed:
            raise ValueError, 'XXX'
        if path in self.resources_added:
            return
        self.resources_changed.add(path)

