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
cwd_sessions_folder = os.path.join(cwd, "sessions")
# Sessions
SESSIONS_STORE_TYPE = os.environ.setdefault("SESSIONS_STORE_TYPE", "ext:database")
SESSIONS_URL = os.environ.setdefault("SESSIONS_URL", f"sqlite:///{cwd_sessions_folder}/sessions.db")
SESSIONS_FOLDER = os.environ.setdefault("SESSIONS_FOLDER", cwd_sessions_folder)
SESSION_TIMEOUT = int(os.environ.setdefault("SESSION_TIMEOUT", "172800"))
SESSION_EXPIRE = int(os.environ.setdefault("SESSION_EXPIRE", "864000"))
SESSION_DOMAIN = os.environ.get("SESSION_DOMAIN", None)
SESSION_SAMESITE = os.environ.setdefault("SESSION_SAMESITE", "Lax")
SESSION_KEY = os.environ.setdefault("SESSION_KEY", "beaker.session.id")
SESSION_SECURE = bool(int(os.environ.get("SESSION_SECURE") or 1))
# JWT
JWT_EXPIRE = int(os.environ.setdefault("JWT_EXPIRE", "172800"))
JWT_ISSUER = os.environ.setdefault("JWT_ISSUER", "ikaaro")

# DEBUG
DEBUG = bool(int(os.environ.get('DEBUG') or 0))
