from plugin_manager import Manager
from quart import Request, Websocket

manager = Manager()


@manager.on('plugin.pre-load')
def on_pre_load():
    print('Plugin Loading')


@manager.on('plugin.loading.endpoints')
def on_loading_endpoints():
    print('Working to load endpoints')


@manager.on('plugin.loading.sockets')
def on_loading_endpoints():
    print('Also sockets!!')


@manager.on('plugin.loaded')
def on_load():
    print('Plugin Loaded!')


@manager.on('server.request')
def on_request(request: Request):
    print(request.full_path)


@manager.on('server.socket')
async def on_socket(ws: Websocket):
    print(ws.full_path)


@manager.on('server.start')
def on_server_start():
    print('The server is starting')


@manager.on('server.end')
def on_server_start():
    print('Sad to say goodbye')


@manager.route('/test')
def c(request: Request) -> tuple[str, int]:
    return 'This is a test', 200


@manager.websocket('/test.ws')
async def wbs(ws: Websocket):
    while True:
        await ws.send('Hello, World!')
