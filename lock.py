# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import datetime
from random import random
from time import time

# Import from itools
from itools.datatypes import DateTime
from itools.handlers import TextFile, register_handler_class
from itools.utils import add_type


class Lock(TextFile):

    class_mimetypes = ['text/x-lock']
    class_extension = 'lock'


    def new(self, username=None, **kw):
        self.username = username
        self.lock_timestamp = datetime.now()
        self.key = '%s-%s-00105A989226:%.03f' % (random(), random(), time())


    def _load_state_from_file(self, file):
        username, timestamp, key = file.read().strip().split('\n')
        self.username = username
        # FIXME Backwards compatibility: remove microseconds first
        timestamp = timestamp.split('.')[0]
        self.lock_timestamp = DateTime.decode(timestamp)
        self.key = key


    def to_str(self):
        timestamp = DateTime.encode(self.lock_timestamp)
        return '%s\n%s\n%s' % (self.username, timestamp, self.key)



###########################################################################
# Register
###########################################################################
register_handler_class(Lock)
for mimetype in Lock.class_mimetypes:
    add_type(mimetype, '.%s' % Lock.class_extension)
