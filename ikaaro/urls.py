# -*- coding: UTF-8 -*-
# Copyright (C) 2017 Taverne Sylvain <taverne.sylvain@gmail.com>
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

# Import from standard library
from importlib import import_module

# Import from itools
from itools.core import prototype



class URLPattern(prototype):

    pattern = None
    view = None

    def get_patterns(self):
        return [(self.pattern, self.view)]



class SubPatterns(prototype):

    base_path = None
    package = None

    def get_patterns(self):
        patterns = []
        try:
            the_module = import_module(self.package)
        except ImportError:
            msg = 'The package {} do not exists'
            raise ImportError(msg.format(self.package))
        for pattern in getattr(the_module, 'urlpatterns'):
            for pattern, view in pattern.get_patterns():
                patterns.append((self.base_path + pattern, view))
        return patterns



def urlpattern(pattern, view):
    return URLPattern(pattern=pattern, view=view)


def subpatterns(base_path, package):
    return SubPatterns(base_path=base_path, package=package)


urlpatterns = [
    subpatterns('/api', 'ikaaro.api.urls')
]
