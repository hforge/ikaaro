# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from itools import vfs

# Import from ikaaro
from metadata import Metadata
from registry import get_object_class



def is_instance_up_to_date(target):
    # Check for the log folder (XXX To remove by 0.21)
    if not vfs.exists('%s/log' % target):
        return False

    # Check for the 'catalog/fields' file (XXX To remove by 0.21)
    if vfs.exists('%s/catalog/fields' % target):
        return False

    # Find out the root class
    metadata = Metadata('%s/database/.metadata' % target)
    cls = get_object_class(metadata.format)
    # Check the version
    if metadata.version < cls.class_version:
        return False

    # All tests pass
    return True
