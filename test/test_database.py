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

# Import from the Standard Library
from unittest import TestCase, main

# Import from itools
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from ikaaro.database import Database, RODatabase
from ikaaro.folder import Folder
from ikaaro.utils import get_base_path_query
from ikaaro.text import Text


class FreeTestCase(TestCase):


    def test_create_text(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = root = database.get_resource('/')
                # Create 1 resource
                container = root.make_resource('test-create-texts', Folder)
                resource = container.make_resource(None, Text)
                self.assertEqual(str(resource.abspath), '/test-create-texts/0')
                metadata = resource.metadata
                self.assertEqual(metadata.format, 'text')
                database.save_changes()
                # Check if resource exists
                resource = root.get_resource('/test-create-texts/0')
                self.assertEqual(resource.name, '0')
                search = database.search(abspath='/test-create-texts/0')
                self.assertEqual(len(search), 1)
                # Del resource
                root.del_resource('/test-create-texts/0')
                database.save_changes()
                # Check if has been removed
                resource = root.get_resource('/test-create-texts/0', soft=True)
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
                self.assertEqual(user.name, '1')
                user.set_value('groups', ['/config/groups/admins'])
                database.save_changes()
                # Try to get user
                user = root.get_resource('/users/1', soft=True)
                self.assertEqual(user.name, '1')
                self.assertEqual(user.get_value('email'), 'test-create-user@hforge.org')
                self.assertEqual(user.authenticate(password), True)
                self.assertEqual(user.authenticate('badpassword'), False)
                # Cannot create 2 users with the same email address
                user = root.make_user(email, password)
                self.assertEqual(user, None)


    def test_multilingual_search(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = root = database.get_resource('/')
                container = root.make_resource('test-multilingual', Folder)
                # Create N resources
                for i in range(0, 20):
                    kw =  {'title':   {'fr': u'Bonjour', 'en': u'Hello'}}
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
                    PhraseQuery('title', u'Hello'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_en', u'Hello'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_fr', u'Bonjour'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 20)
                query = AndQuery(
                    PhraseQuery('format', 'text'),
                    PhraseQuery('title_es', u'Hola'),
                    get_base_path_query('/test-multilingual'),
                    )
                search = database.search(query)
                self.assertEqual(len(search), 0)
                # Close database
                database.close()


    def test_move_file(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
                       'data': 'this is text'}
                root = database.get_resource('/')
                container = root.make_resource('test-move', Folder)
                resource = container.make_resource(None, Text, **kw)
                self.assertEqual(str(resource.abspath), '/test-move/0')
                database.save_changes()
                # Move '/0' to '/1'
                root.move_resource('/test-move/0', '/test-move/1')
                self.assertEqual(root.get_resource('/test-move/0', soft=True), None)
                self.assertEqual(root.get_resource('/test-move/1').name, '1')
                # Move '/1' to '/1'
                root.move_resource('/test-move/1', '/test-move/1')
                self.assertEqual(root.get_resource('/test-move/1').name, '1')
                # Check text
                r1 = root.get_resource('/test-move/1')
                data = r1.get_value('data').to_str()
                self.assertEqual(data, 'this is text')
                database.close()


    def test_move_folder(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'}}
                container = root.make_resource('folder1', Folder, **kw)
                child = container.make_resource('child', Folder)
                child.make_resource('hello_child.txt', Text)
                container.make_resource('hello.txt', Text)
                self.assertEqual(
                    database.added,
                    set(['folder1.metadata', 'folder1/hello.txt.metadata',
                         'folder1/child.metadata', 'folder1/child/hello_child.txt.metadata']))
                root.move_resource('folder1', 'folder2')
                self.assertEqual(root.get_resource('folder1', soft=True), None)
                self.assertEqual(root.get_resource('folder2').name, 'folder2')
                self.assertEqual(root.get_resource('folder2/hello.txt').abspath, '/folder2/hello.txt')
                self.assertEqual(
                    database.added,
                    set(['folder2.metadata', 'folder2/hello.txt.metadata',
                         'folder2/child.metadata', 'folder2/child/hello_child.txt.metadata']))
                database.close()


    def test_abort_transaction(self):
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
                       'data': 'this is text'}
                resource = root.make_resource(None, Text, **kw)
                self.assertEqual(str(resource.abspath), '/0')
                self.assertNotEqual(root.get_resource('/0'), None)
                database.save_changes()
                resource = root.make_resource(None, Text, **kw)
                self.assertEqual(str(resource.abspath), '/1')
                database.catalog.index_document({'abspath': '/2'})
                database.abort_changes()
                self.assertNotEqual(root.get_resource('/0'), None)
                self.assertEqual(root.get_resource('/1', soft=True), None)
                database.close()


    def test_close_transaction(self):
        """
        Test if flush is done when we close database
        """
        with Database('demo.hforge.org', 19500, 20500) as database:
            with database.init_context():
                root = database.get_resource('/')
                container = root.make_resource('folder-test-close-transaction', Folder)
                kw =  {'title': {'fr': u'Bonjour', 'en': u'Hello'},
                       'data': 'this is text'}
                resource = container.make_resource(None, Text, **kw)
                self.assertEqual(str(resource.abspath), '/folder-test-close-transaction/0')
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
                    set(['folder-to-remove.metadata', 'folder-to-remove/1.metadata',
                         'folder-to-remove/2.metadata', 'folder-to-remove/3.metadata']))
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
                    set([
                      'folder-to-copy-1.metadata', 'folder-to-copy-1/1.metadata',
                      'folder-to-copy-1/1/subchild.metadata', 'folder-to-copy-1/2.metadata',
                      'folder-to-copy-2.metadata', 'folder-to-copy-2/1.metadata',
                      'folder-to-copy-2/1/subchild.metadata', 'folder-to-copy-2/2.metadata',
                      ]))


if __name__ == '__main__':
    main()
