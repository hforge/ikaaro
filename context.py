# -*- coding: UTF-8 -*-
# Copyright (C) 2011 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from os.path import isdir

# Import from itools
from itools.fs import lfs
from itools.handlers import ro_database
from itools.i18n import has_language
from itools.uri import get_host_from_authority, normalize_path
from itools.web import Context


class CMSContext(Context):

    set_mtime = True
    message = None
    content_type = None


    def find_site_root(self):
        # Default to root
        root = self.root
        self.site_root = root

        # Check we have a URI
        uri = self.uri
        if uri is None:
            return

        # The site root depends on the host
        hostname = get_host_from_authority(uri.authority)

        catalog = self.database.catalog
        # This may happen with a broken or missing catalog in
        # icms-update-catalog.py
        if not catalog:
            return

        results = catalog.search(vhosts=hostname)
        if len(results) == 0:
            return

        documents = results.get_documents()
        path = documents[0].abspath
        self.site_root = root.get_resource(path)

    def get_template(self, web_path):
        web_path = normalize_path(web_path)

        # 1. Find local root
        web_roots = ui_registry.keys()
        web_roots.sort(reverse=True)
        for web_root in web_roots:
            if web_path.startswith(web_root):
                break
        else:
            raise ValueError, 'unexpected %s' % repr(web_path)

        # 2. Get the local path
        local_root = ui_registry[web_root]
        local_path = local_root + web_path[len(web_root):]

        # 3. Get the handler
        handler = ro_database.get_handler(local_path, soft=True)
        if handler:
            return handler

        # 4. Not an exact match: trigger language negotiation
        folder_path, name = local_path.rsplit('/', 1)
        name = name + '.'
        n = len(name)
        languages = []
        for x in lfs.get_names(folder_path):
            if x[:n] == name:
                language = x[n:]
                if has_language(language):
                    languages.append(language)
        if not languages:
            return None

        # 4.1 Get the best variant
        accept = self.accept_language
        language = accept.select_language(languages)

        # 4.2 By default use whatever variant
        # (XXX we need a way to define the default)
        if language is None:
            language = languages[0]
        local_path = '%s.%s' % (local_path, language)
        return ro_database.get_handler(local_path)


###########################################################################
# Registry
###########################################################################
def _fix_path(path):
    if type(path) is not str:
        raise TypeError, 'unexpected %s' % repr(path)
    path = normalize_path(path)
    if not path or path[0] != '/':
        raise ValueError, 'unexpected %s' % repr(path)

    return path if path[-1] == '/' else path + '/'


ui_registry = {}
def register_ui(web_root, local_root):
    web_root = _fix_path(web_root)
    local_root = _fix_path(local_root)
    if not isdir(local_root):
        raise ValueError, 'unexpected %s' % repr(local_root)
    ui_registry[web_root] = local_root
