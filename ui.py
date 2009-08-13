# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.core import get_abspath
from itools.gettext import MSG
from itools.handlers import File, Folder, Image, RODatabase
from itools.http import NotFound, get_context
from itools.i18n import has_language
from itools.uri import Path
from itools.web import BaseView
from itools.xmlfile import XMLFile

# Import from ikaaro
from app import mount
from resource_ import IResource


ui_database = RODatabase(fs=lfs)



class FileGET(BaseView):

    access = True


    def get_mtime(self, resource):
        return resource.get_mtime()


    def GET(self, resource, context):
        context.content_type = resource.get_mimetype()
        return resource.to_str()



class UIFile(IResource, File):

    database = ui_database
    clone_exclude = File.clone_exclude | frozenset(['parent', 'name'])


    download = FileGET()

    def get_view(self, name, query=None):
        if name is None:
            return self.download
        raise NotFound



class UIImage(Image, UIFile):
    pass



class UITemplate(UIFile, XMLFile):
    pass



map = {
    'application/xml': UITemplate,
    'application/xhtml+xml': UITemplate,
    'text/xml': UITemplate,
    'image/png': UIImage,
    'image/jpeg': UIImage,
}



class UIFolder(IResource, Folder):

    database = ui_database
    class_title = MSG(u'UI')
    class_icon48 = 'icons/48x48/folder.png'


    def _get_names(self):
        # FIXME May not be the right implementation
        return self.get_handler_names()


    def _get_resource(self, name):
        if self.has_handler(name):
            handler = self.get_handler(name)
        else:
            name = '%s.' % name
            n = len(name)
            languages = []
            for x in self.get_handler_names():
                if x[:n] == name:
                    language = x[n:]
                    if has_language(language):
                        languages.append(language)

            if not languages:
                return None

            # Get the best variant
            context = get_context()
            if context is None:
                language = None
            else:
                accept = context.accept_language
                language = accept.select_language(languages)

            # By default use whatever variant
            # (XXX we need a way to define the default)
            if language is None:
                language = languages[0]
            handler = self.get_handler('%s%s' % (name, language))

        if isinstance(handler, Folder):
            handler = UIFolder(handler.key)
        else:
            format = handler.get_mimetype()
            cls = map.get(format, UIFile)
            handler = cls(handler.key)
        handler.database = self.database
        return handler



#############################################################################
# The folder "/ui"
#############################################################################

skin_registry = {}
def register_skin(name, skin):
    skin_registry[name] = UIFolder(skin)
    mount('/ui/%s' % name, skin)


# Register the built-in skins
ui_path = get_abspath('ui')
mount('/ui', ui_path)
register_skin('aruni', '%s/aruni' % ui_path)


class UI(UIFolder):

    def _get_resource(self, name):
        if name in skin_registry:
            skin = skin_registry[name]
            return skin
        return UIFolder._get_resource(self, name)


    def get_canonical_path(self):
        return Path('/ui')
