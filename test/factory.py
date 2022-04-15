# Import from external
import shutil

# Import from ikaaro
from ikaaro.server import Server, create_server


def create_server_test(path='www.hforge.org', email='test@example.com', password='password',
                       root=None, modules=None,
                       listen_port=8081):

    if modules is None:
        modules = []

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
    return server