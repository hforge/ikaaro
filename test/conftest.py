import pathlib
import shutil

# Requirements
from starlette.testclient import TestClient
import pytest

# Import from itools
from itools.fs import lfs

# Import from ikaaro
from ikaaro.database import Database
from ikaaro.server import Server, create_server
from ikaaro import asgi


BASE_DIR = pathlib.Path(__file__).resolve().parent

@pytest.fixture
def client():
    return TestClient(asgi.application)

@pytest.fixture(scope='session')
async def demo():
    path = str(BASE_DIR / 'demo.hforge.org')
    if lfs.exists(path):
        lfs.remove(path)

    await create_server(path, 'test@hforge.org', 'password', 'ikaaro',
                        website_languages=['en', 'fr'])

    return path


@pytest.fixture
def database(demo):
    with Database(demo, 19500, 20500) as database:
        yield database


@pytest.fixture
async def server(demo):
    with Server(demo) as server:
        yield server


@pytest.fixture
def auth(server):
    client = TestClient(asgi.application)

    data = {'loginname': 'test@hforge.org', 'password': 'password'}
    client.post('/;login', data=data, follow_redirects=False)
    client.cookies = dict(client.cookies)  # FIXME This line should not be needed

    return client


@pytest.fixture
async def hforge_server():
    path = str(BASE_DIR / 'www.hforge.org')
    email = 'test@example.com'
    password = 'password'
    root = None
    modules = []
    listen_port = 8081

    shutil.rmtree(path, ignore_errors=True)
    shutil.rmtree('sessions', ignore_errors=True)
    await create_server(
        target=path,
        email=email,
        password=password,
        root=root,
        modules=modules,
        listen_port=listen_port,
        backend="git"
    )
    with Server(path) as server:
        yield server
