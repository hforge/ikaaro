# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Sylvain Taverne <taverne.sylvain@gmail.com>
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
from pprint import pprint
import sys

# Import from ikaaro
from ikaaro.server import Server, create_server
from ikaaro.root import Root
import shutil

path = 'www.hforge.org'
email = 'test@example.com'
password = 'password'
root = None
modules = []
listen_port = 8081


if sys.argv[-1] == 'create':
    shutil.rmtree(path, ignore_errors=True)
    shutil.rmtree('sessions', ignore_errors=True)
    create_server(
        target=path,
        email=email,
        password=password,
        root=root,
        modules=modules,
        listen_port=listen_port,
        backend="git"
    )

server = Server(path)
server.start(detach=False, loop=False)
print('Launch reindexation')
reindex_success = server.reindex_catalog(quiet=True)
if reindex_success:
    print('Reindex was successfull')
else:
    print('Error in reindexation')
retour = server.do_request('GET', '/;_ctrl')
print(retour)
server.stop()
