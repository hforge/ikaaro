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
from unittest import TestCase, main

# Import from itools
from itools.database import Metadata, MetadataProperty
from itools.fs import lfs

# Import from ikaaro
from ikaaro.webpage import WebPage


metadata_str = """
format;version=20090122:webpage
title;lang=en:hello
title;lang=fr:bonjur
title;lang=fr:bonjour
"""


class LoadTestCase(TestCase):

    def setUp(self):
        self.metadata = Metadata(string=metadata_str, cls=WebPage)


    def test_format(self):
        format = self.metadata.format
        self.assertEqual(format, 'webpage')


    def test_version(self):
        value = self.metadata.version
        self.assertEqual(value, '20090122')


    def test_title(self):
        value = self.metadata.get_property('title', language='fr').value
        self.assertEqual(type(value), unicode)
        self.assertEqual(value, u'bonjour')



class NewTestCase(TestCase):

    def setUp(self):
        metadata = Metadata(cls=WebPage)
        title = MetadataProperty(u'Hello World', lang='en')
        metadata.set_property('title', title)
        self.metadata = metadata
        # Sandbox
        lfs.make_folder('sandbox')


    def tearDown(self):
        if lfs.exists('sandbox'):
            lfs.remove('sandbox')


    def test_format(self):
        format = self.metadata.format
        self.assertEqual(format, WebPage.class_id)


    def test_version(self):
        value = self.metadata.version
        self.assertEqual(value, WebPage.class_version)


    def test_title(self):
        value = self.metadata.get_property('title', language='en').value
        self.assertEqual(type(value), unicode)
        self.assertEqual(value, u'Hello World')


    def test_save(self):
        self.metadata.save_state_to('sandbox/metadata')
        # TODO



###########################################################################
# Test extensible schema
###########################################################################
class OpenWebPage(WebPage):

    class_id = 'open-webpage'
    fields_soft = True



good_metadata = """
format;version=20090122:open-webpage
title;lang=en:hello
title;lang=fr:bonjur
title;lang=fr:bonjour
free_title:bye
"""

bad_metadata = """
format;version=20090122:webpage
title;lang=en:hello
title;lang=fr:bonjur
title;lang=fr:bonjour
free_title:bye
free_title:au revoir
"""



class FreeTestCase(TestCase):

    def test_good(self):
        metadata = Metadata(string=good_metadata, cls=OpenWebPage)
        prop = metadata.get_property('free_title')
        self.assertEqual(prop[0].value, 'bye')


    def test_bad(self):
        self.assertRaises(ValueError, Metadata, string=bad_metadata, cls=WebPage)



if __name__ == '__main__':
    main()
