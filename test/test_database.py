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

# Import from the Standard Library
from unittest import TestCase, main
from datetime import time

# Import from itools
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from ikaaro.database import Database
from ikaaro.folder import Folder
from ikaaro.file import File
from ikaaro.utils import get_base_path_query
from ikaaro.text import Text
import ikaaro.root


class FreeTestCase(TestCase):

    def test_create_text(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                # Create 1 resource
                container = root.make_resource('test-create-texts', Folder)
                resource = container.make_resource(None, Text)
                path = str(resource.abspath)
                metadata = resource.metadata
                self.assertEqual(metadata.format, 'text')
                database.save_changes()
                # Check if resource exists
                resource = root.get_resource(path)
                self.assertEqual(len(resource.name), 32)
                search = database.search(abspath=path)
                self.assertEqual(len(search), 1)
                # Del resource
                root.del_resource(path)
                database.save_changes()
                # Check if has been removed
                resource = root.get_resource(path, soft=True)
                self.assertEqual(resource, None)
                search = database.search(abspath='/test-create-texts/1')
                self.assertEqual(len(search), 0)


    def test_create_user(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                # Create a new user
                email = 'test-create-user@hforge.org'
                password = 'password'
                user = root.make_user(email, password)
                self.assertEqual(len(user.name), 32)
                user.set_value('groups', ['/config/groups/admins'])
                database.save_changes()
                # Try to get user
                user = root.get_resource(f'/users/{user.name}', soft=True)
                self.assertEqual(len(user.name), 32)
                self.assertEqual(user.get_value('email'), 'test-create-user@hforge.org')
                self.assertEqual(user.authenticate(password), True)
                self.assertEqual(user.authenticate('badpassword'), False)
                # Cannot create 2 users with the same email address
                user = root.make_user(email, password)
                self.assertEqual(user, None)


    def test_create_two_resources_at_root(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                f1 = root.make_resource(None,  Folder)
                self.assertEqual(len(f1.name), 32)
                self.assertEqual(database.added, {f'{f1.name}.metadata'})
                f2 = root.make_resource(None,  Folder)
                self.assertEqual(len(f2.name), 32)


    def test_create_two_resources_in_folder(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('test-two-resources', Folder)
                self.assertEqual(root.get_resource('test-two-resources').name, 'test-two-resources')
                f1 = container.make_resource(None,  Folder)
                self.assertEqual(len(f1.name), 32)
                self.assertEqual(database.added, {
                    'test-two-resources.metadata',
                    f'test-two-resources/{f1.name}.metadata'
                })
                f2 = container.make_resource(None,  Folder)
                self.assertEqual(len(f2.name), 32)
                self.assertEqual(database.added, {
                    'test-two-resources.metadata',
                    f'test-two-resources/{f1.name}.metadata',
                    f'test-two-resources/{f2.name}.metadata'
                })


    def test_multilingual_search(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('test-multilingual', Folder)
                # Create N resources
                for i in range(0, 20):
                    kw =  {'title':   {'fr': 'Bonjour', 'en': 'Hello'}}
                    container.make_resource(str(i), Text, **kw)
                database.save_changes()
                # Check if resource exists
                query = AndQuery(
                    get_base_path_query('/test-multilingual'),
                    PhraseQuery('format', 'text'))
                search = database.search(query)
                self.assertEqual(len(search), 20)
                # Check if resource exists
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title', 'Hello'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_en', 'Hello'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_fr', 'Bonjour'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_es', 'Hola'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 0)
                # Close database
                database.close()


    def test_move_file(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                kw =  {'title': {'fr': 'Bonjour', 'en': 'Hello'},
                       'data': 'this is text'}
                root = database.get_resource('/')
                container = root.make_resource('test-move', Folder)
                resource = container.make_resource(None, Text, **kw)
                self.assertEqual(len(resource.name), 32)
                self.assertEqual(str(resource.abspath), f'/test-move/{resource.name}')
                database.save_changes()
                # Move '/0' to '/1'
                root.move_resource(f'/test-move/{resource.name}', '/test-move/1')
                self.assertEqual(root.get_resource(f'/test-move/{resource.name}', soft=True), None)
                self.assertEqual(root.get_resource('/test-move/1').name, '1')
                # Move '/1' to '/1'
                root.move_resource('/test-move/1', '/test-move/1')
                self.assertEqual(root.get_resource('/test-move/1').name, '1')
                # Check text
                r1 = root.get_resource('/test-move/1')
                data = r1.get_value('data').to_text()
                self.assertEqual(data, 'this is text')
                database.close()


    def test_move_folder(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                kw =  {'title': {'fr': 'Bonjour', 'en': 'Hello'}}
                container = root.make_resource('folder1', Folder, **kw)
                child = container.make_resource('child', Folder)
                child.make_resource('hello_child.txt', Text)
                container.make_resource('hello.txt', Text)
                self.assertEqual(
                    database.added,
                    {'folder1.metadata', 'folder1/hello.txt.metadata',
                         'folder1/child.metadata', 'folder1/child/hello_child.txt.metadata'})
                root.move_resource('folder1', 'folder2')
                self.assertEqual(root.get_resource('folder1', soft=True), None)
                self.assertEqual(root.get_resource('folder2').name, 'folder2')
                self.assertEqual(root.get_resource('folder2/hello.txt').abspath, '/folder2/hello.txt')
                self.assertEqual(
                    database.added,
                    {'folder2.metadata', 'folder2/hello.txt.metadata',
                         'folder2/child.metadata', 'folder2/child/hello_child.txt.metadata'})
                database.close()


#   def test_set_bad_value(self):
#       with Database('demo.hforge.org', 19500, 20500) as database:
#           with database.init_context():
#               root = database.get_resource('/')
#               e = None
#               try:
#                   root.set_value('mtime', time(10, 0))
#               except Exception as e:
#                   pass
#               self.assertNotEqual(e, None)


    def test_abort_transaction(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                kw =  {'title': {'fr': 'Bonjour', 'en': 'Hello'},
                       'data': 'this is text'}
                r1 = root.make_resource(None, Text, **kw)
                self.assertEqual(str(r1.abspath), f'/{r1.name}')
                self.assertIsNotNone(root.get_resource(f'/{r1.name}'))
                database.save_changes()
                r2 = root.make_resource(None, Text, **kw)
                self.assertEqual(str(r2.abspath), f'/{r2.name}')
                database.catalog.index_document({'abspath': '/2'})
                database.abort_changes()
                self.assertIsNotNone(root.get_resource(f'/{r1.name}'))
                self.assertIsNone(root.get_resource(f'/{r2.name}', soft=True))
                database.close()


    def test_close_transaction(self):
        """
        Test if flush is done when we close database
        """
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('folder-test-close-transaction', Folder)
                kw =  {'title': {'fr': 'Bonjour', 'en': 'Hello'},
                       'data': 'this is text'}
                resource = container.make_resource(None, Text, **kw)
                self.assertEqual(str(resource.abspath), f'/folder-test-close-transaction/{resource.name}')
                database.save_changes()
                query = AndQuery(
                    get_base_path_query('/folder-test-close-transaction'),
                    PhraseQuery('format', 'text'))
                search = database.search(query)
                self.assertEqual(len(search), 1)
                resource = root.make_resource(None, Text)
                database.close()
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                query = AndQuery(
                    get_base_path_query('/folder-test-close-transaction'),
                    PhraseQuery('format', 'text'))
                search = database.search(query)
                self.assertEqual(len(search), 1)
                self.assertEqual(root.get_resource('/folder-test-close-transaction/1', soft=True), None)



    def test_root(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                self.assertEqual(root.metadata.format, 'iKaaro')


    def test_create_folders(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('folder-test-create-folders', Folder)
                container.make_resource('1', Text)
                container.make_resource('2', Text)
                container.make_resource('3', Text)
                names = sorted(container.get_names())
                self.assertEqual(names, ['1', '2', '3'])


    def test_remove_folder(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context() as context:
                root = database.get_resource('/')
                container = root.make_resource('folder-to-remove', Folder)
                container.make_resource('1', Text)
                container.make_resource('2', Text)
                container.make_resource('3', Text)
                context.database.save_changes()
                root.del_resource('folder-to-remove')
                self.assertEqual(
                    database.removed,
                    {'folder-to-remove.metadata', 'folder-to-remove/1.metadata',
                         'folder-to-remove/2.metadata', 'folder-to-remove/3.metadata'})
                self.assertEqual(root.get_resource('folder-to-remove', soft=True), None)
                self.assertEqual(root.get_resource('folder-to-remove/1', soft=True), None)
                self.assertEqual(root.get_resource('folder-to-remove/2', soft=True), None)
                self.assertEqual(root.get_resource('folder-to-remove/3', soft=True), None)


    def test_copy_folder(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('folder-to-copy-1', Folder)
                container_child = container.make_resource('1', Folder)
                container_child.make_resource('subchild', Text)
                container.make_resource('2', Text)
                root.copy_resource('folder-to-copy-1', 'folder-to-copy-2')
                self.assertEqual(
                    database.added,
                    {
                      'folder-to-copy-1.metadata', 'folder-to-copy-1/1.metadata',
                      'folder-to-copy-1/1/subchild.metadata', 'folder-to-copy-1/2.metadata',
                      'folder-to-copy-2.metadata', 'folder-to-copy-2/1.metadata',
                      'folder-to-copy-2/1/subchild.metadata', 'folder-to-copy-2/2.metadata',
                      })


    def test_cache_error_on_move(self):
        with Database('demo.hforge.org', 10, 20) as database:
            l = []
            with database.init_context() as context:
                for i in range(0, 50):
                    root = database.get_resource('/')
                    name = f'test-cache-error-on-move-{i}'
                    container = root.make_resource(name, File)
                    container.set_value('data', 'bytes')
                    l.append(container)
                    context.database.save_changes()
                    container.parent.move_resource(name, name + 'newname')



if __name__ == '__main__':
    main()
