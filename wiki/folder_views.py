# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2008 Gautier Hayoun <gautier.hayoun@itaapy.com>
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
from itools.gettext import MSG
from itools.uri import get_reference
from itools.web import BaseView

# Import from ikaaro
from ikaaro.views import ContextMenu
from page import WikiPage


class WikiMenu(ContextMenu):

    title = MSG(u'Wiki')

    def get_items(self, resource, context):
        # If called from a child
        if isinstance(resource, WikiPage):
            resource = resource.parent
        # Namespace
        base = context.get_link(resource)
        return [
            {'title': resource.get_view(view).title,
             'href': '%s/;%s' % (base, view)}
            for view in resource.class_views ]

