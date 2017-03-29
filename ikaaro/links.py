# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Sylvain Taverne <taverne.sylvain@gmail.coù>
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

# Import from ikaaro
from utils import split_reference


def update_abspath_links(self, resource, field_name, source, target, languages,
                 old_base, new_base):
    if not self.multilingual:
        languages = [None]

    for lang in languages:
        value = resource.get_value(field_name, lang)
        if not value:
            continue
        if self.multiple:
            # Multiple
            new_values = []
            for x in value:
                if not x:
                    continue
                if not x.startswith('/'):
                    # In Share_Field, "everybody" / "authenticated" are not abspaths
                    new_values.append(x)
                else:
                    # Get the reference, path and view
                    ref, path, view = split_reference(x)
                    if ref.scheme:
                        continue
                    path = old_base.resolve2(path)
                    if path == source:
                        # Explicitly call str because URI.encode does
                        # nothing
                        new_value = str(target) + view
                        new_values.append(new_value)
                    else:
                        new_values.append(x)
            self._set_value(resource, field_name, new_values, lang)
        else:
            # Singleton
            if not value.startswith('/'):
                # In Share_Field, "everybody" / "authenticated" are not abspaths
                continue
            # Get the reference, path and view
            ref, path, view = split_reference(value)
            if ref.scheme:
                continue
            path = old_base.resolve2(path)
            if path == source:
                # Hit the old name
                # Build the new reference with the right path
                # Explicitly call str because URI.encode does nothing
                new_value = str(target) + view
                self._set_value(resource, field_name, new_value, lang)


def get_abspath_links(self, links, resource, field_name, languages):
    if not self.multilingual:
        languages = [None]

    for lang in languages:
        value = resource.get_value(field_name, lang)
        if not value:
            continue
        if self.multiple:
            # Multiple
            for x in value:
                if not x:
                    continue
                if x.startswith('/'):
                    # Get the reference, path and view
                    ref, path, view = split_reference(x)
                    if ref.scheme:
                        continue
                    links.add(str(path))
        else:
            if value.startswith('/'):
                # Get the reference, path and view
                ref, path, view = split_reference(value)
                if ref.scheme:
                    continue
                # Singleton
                links.add(str(path))
    return links
