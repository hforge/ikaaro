from unittest import TestCase

# Import from itools
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.text import Text

from factory import create_server_test

class UserHistoryFolder(Folder):
    """
        Class to test xapian s
    """

    class_id = 'user-history'


class TestXapianSearch(TestCase):

    def setUp(self) -> None:
        self.server = create_server_test()

    def test_user_search(self):
        with self.server.database as database:
            database.init_context()
            # Test /;ctrl view
            retour = self.server.do_request('GET', '/;_ctrl')
            assert retour['status'] == 200
            root = database.get_resource('/')
            email = 'test-create-user@hforge.org'
            password = 'password'
            user = root.make_user(email, password)
            root.make_resource(f"users/{user.name}/toto", Text)

            container = root.make_resource('test-create-texts', Folder)
            sub_container = container.make_resource('users', Folder)
            sub_container_2 = sub_container.make_resource(user.name, UserHistoryFolder)
            sub_container_2.make_resource("device", Text)
            self.server.database.save_changes()
            query = AndQuery(
                PhraseQuery("format", "user"),
                PhraseQuery("abspath", str(user.abspath))
            )
            search = database.search(query)
            self.assertEqual(len(search.get_documents()), 1)

