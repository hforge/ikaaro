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

# Import from itools
from itools.core import freeze, proto_lazy_property
from itools.fs import lfs
from itools.handlers import ro_database
from itools.i18n import has_language
from itools.uri import Path, normalize_path
from itools.web import Context

# Import from ikaaro
from skins import skin_registry


class CMSContext(Context):

    set_mtime = True
    message = None
    content_type = None
    is_cron = False


    def init_context(self):
        # Init context
        super(CMSContext, self).init_context()
        # Set CRON flag
        self.is_cron = False


    def come_back(self, message, goto=None, keep=freeze([]), **kw):
        goto = super(CMSContext, self).come_back(message, goto, keep, **kw)
        # Keep fancybox
        if 'fancybox' in self.uri.query:
            goto.query['fancybox'] = '1'
        # Ok
        return goto


    @proto_lazy_property
    def root(self):
        return self.database.get_resource('/')


    def find_site_root(self):
        self.site_root = self.root


    def get_template(self, web_path):
        warning = None
        web_path_object = Path(normalize_path(web_path))
        skin_name = web_path_object[1]
        try:
            skin = skin_registry[skin_name]
        except KeyError:
            warning = 'WARNING: web_path {} is obsolete use /ui/ikaaro/'
            warning = warning.format(web_path)
            web_path = web_path.replace('/ui/', '/ui/ikaaro/')
            skin = skin_registry['ikaaro']
        # 1) Try with envionment skin
        skin_key = skin.get_environment_key(self.server)
        web_path = web_path.replace(skin.base_path, '')
        template = self.get_template_from_skin_key(skin_key, web_path, warning)
        if template:
            return template
        # 2) Try with standard skin
        return self.get_template_from_skin_key(skin.key, web_path, warning)


    def get_template_from_skin_key(self, skin_key, web_path, warning):
        local_path = skin_key + web_path
        # 3. Get the handler
        handler = ro_database.get_handler(local_path, soft=True)
        if handler:
            if warning:
                print warning
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
        # Print Warning
        if warning:
            print warning
        # 4.2 By default use whatever variant
        # (XXX we need a way to define the default)
        if language is None:
            language = languages[0]
        local_path = '%s.%s' % (local_path, language)
        return ro_database.get_handler(local_path)


    #######################################################################
    # Search
    def _user_search(self, user):
        access = self.root.get_resource('/config/access')
        query = access.get_search_query(user, 'view')
        return self.database.search(query)


    @proto_lazy_property
    def _context_user_search(self):
        return self._user_search(self.user)


    def search(self, query=None, user=None, **kw):
        if self.is_cron:
            # If the search is done by a CRON we don't
            # care about the default ACLs rules
            return self.database.search(query)
        if user is None:
            return self._context_user_search.search(query, **kw)
        return self._user_search(user).search(query, **kw)
