# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools.handlers import File
from itools.http import ClientError, set_context
from itools.soup import SoupMessage
from itools.uri import Path
from itools import vfs
from itools.web import WebApplication, lock_body
from itools.web import Resource, BaseView

# Import from ikaaro
from context import CMSContext
from database import get_database
from exceptions import ConsistencyError



class CMSApplication(WebApplication):

    context_class = CMSContext

    def __init__(self, target, size_min, size_max, read_only, index_text):
        self.target = target
        self.database = get_database(target, size_min, size_max, read_only)
        self.index_text = index_text


    def get_context(self, soup_message, path):
        context = WebApplication.get_context(self, soup_message, path)
        context.database = self.database
        context.message = None
        context.content_type = None
        return context


    def get_fake_context(self):
        soup_message = SoupMessage()
        context = self.get_context(soup_message, '/')
        set_context(context)
        return context

