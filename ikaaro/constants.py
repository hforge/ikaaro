# -*- coding: UTF-8 -*-
# Copyright (C) 2020 Mathieu Péquin <mat.pequin@gmail.com>
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
import os


cwd = os.getcwd()
# Sessions
SESSIONS_STORE_TYPE = os.environ.setdefault("SESSIONS_STORE_TYPE", "file")
SESSIONS_FOLDER = os.environ.setdefault("SESSIONS_FOLDER", os.path.join(cwd, "sessions"))
SESSION_TIMEOUT = int(os.environ.setdefault("SESSION_TIMEOUT", "172800"))
SESSION_EXPIRE = int(os.environ.setdefault("SESSION_EXPIRE", "864000"))
SESSION_DOMAIN = os.environ.get("SESSION_DOMAIN", None)
SESSION_SAMESITE = os.environ.setdefault("SESSION_SAMESITE", "Strict")
# JWT
JWT_EXPIRE = int(os.environ.setdefault("JWT_EXPIRE", "172800"))
JWT_ISSUER = os.environ.setdefault("JWT_ISSUER", "ikaaro")
