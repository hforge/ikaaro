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

# Import from the Standard Library
from datetime import datetime
from unittest import TestCase, main

# Import from ikaaro
from ikaaro.metadata_ng import MetadataNG


metadata_str = """
format:webpage
version:20090122
title;lang=en:hello
title;lang=fr:bonjur
title;lang=fr:bonjour
"""




class MetadataTestCase(TestCase):

    def test_parse(self):
        metadata = MetadataNG(string=metadata_str)
        self.assertEqual(metadata.format, 'webpage')
        self.assertEqual(
            metadata.get_property('version').value, '20090122')



if __name__ == '__main__':
    main()
