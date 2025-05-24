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

import pytest

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

def test_metadata_load():
    metadata = Metadata(string=metadata_str, cls=WebPage)
    assert metadata.format == 'webpage'
    assert metadata.version == '20090122'
    title = metadata.get_property('title', language='fr').value
    assert type(title) is str
    assert title == 'bonjour'


def test_metadata_new():
    metadata = Metadata(cls=WebPage)
    title = MetadataProperty('Hello World', lang='en')
    metadata.set_property('title', title)
    # Sandbox
    lfs.make_folder('sandbox')

    try:
        assert metadata.format == WebPage.class_id
        assert metadata.version == WebPage.class_version
        title = metadata.get_property('title', language='en').value
        assert type(title) is str
        assert title == 'Hello World'

        metadata.save_state_to('sandbox/metadata')
        # TODO
    finally:
        if lfs.exists('sandbox'):
            lfs.remove('sandbox')



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


def test_free():
    # Good
    metadata = Metadata(string=good_metadata, cls=OpenWebPage)
    prop = metadata.get_property('free_title')
    assert prop[0].value == 'bye'

    # Bad
    with pytest.raises(ValueError):
        Metadata(string=bad_metadata, cls=WebPage)
