# Import from itools
from itools.database import AndQuery, PhraseQuery

# Import from ikaaro
from ikaaro.folder import Folder
from ikaaro.text import Text


class UserHistoryFolder(Folder):
    class_id = 'user-history'


async def test_user_search(client, hforge_server):
    server = hforge_server

    response = client.get('/;_ctrl')
    assert response.status_code == 200

    async with server.database.init_context():
        root = server.database.get_resource('/')
        email = 'test-create-user@hforge.org'
        password = 'password'
        user = root.make_user(email, password)
        root.make_resource(f"users/{user.name}/toto", Text)

        container = root.make_resource('test-create-texts', Folder)
        sub_container = container.make_resource('users', Folder)
        sub_container_2 = sub_container.make_resource(user.name, UserHistoryFolder)
        sub_container_2.make_resource("device", Text)
        server.database.save_changes()
        query = AndQuery(
            PhraseQuery("format", "user"),
            PhraseQuery("abspath", str(user.abspath))
        )
        search = server.database.search(query)
        assert len(search.get_documents()) == 1
