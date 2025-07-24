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

from importlib import import_module



class URLPattern:
    """Url pattern composed of the path pattern and the view."""

    def __init__(self, pattern, view):
        self.pattern = pattern
        self.view = view

    def get_patterns(self):
        return [(self.pattern, self.view)]


class SubPatterns:
    """Register a base path linked to an url file of url patterns."""

    def __init__(self, base_path, package):
        self.base_path = base_path
        self.package = package

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
    """Helper method to register Urlpatterns as a list in url files."""
    return URLPattern(pattern=pattern, view=view)


def subpatterns(base_path, package):
    """Helper method to register Subpatterns as a list in url files."""
    return SubPatterns(base_path=base_path, package=package)


urlpatterns = [
    subpatterns('/api', 'ikaaro.api.urls')
]
