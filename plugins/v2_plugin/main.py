from plugin_manager import Manager
from quart import Request, Websocket

manager = Manager()


@manager.on('plugin.loaded')
def on_load():
    print('Plugin Loaded!')


@manager.route('/x', enable_lru_cache=True)
async def x(request: Request) -> tuple[str, int]:
    return 'X', 200


@manager.websocket('/echo')
async def echo(ws: Websocket) -> None:
    while True:
        data = await ws.receive()
        await ws.send(data)

# @manager.on('plugin.pre-load')
# def on_pre_load():
#     print('Plugin Loading')
#
#
# @manager.on('plugin.loading.pre-endpoints')
# def on_loading_endpoints():
#     print('Loading endpoints')
#
#
# @manager.on('plugin.loading.post-endpoints')
# def on_loading_endpoints():
#     print('Endpoints loaded')
#
#
# @manager.on('plugin.loading.pre-sockets')
# def on_loading_endpoints():
#     print('Also sockets!!')
#
#
# @manager.on('plugin.loading.post-sockets')
# def on_loading_endpoints():
#     print('Sockets are here!')
#
#
# @manager.on('plugin.loaded')
# def on_load():
#     print('Plugin Loaded!')
#
#
# @manager.on('server.request')
# def on_request(request: Request):
#     print(request.full_path)
#
#
# @manager.on('server.socket')
# async def on_socket(ws: Websocket):
#     print(ws.full_path)
#
#
# @manager.on('server.start')
# def on_server_start():
#     print('The server is starting')
#
#
# @manager.on('server.end')
# def on_server_start():
#     print('Sad to say goodbye')
#
#
# @manager.route('/test')
# def c(request: Request) -> tuple[str, int]:
#     return 'This is a test', 200
#
#
# @manager.websocket('/test.ws')
# async def wbs(ws: Websocket):
#     while True:
#         await ws.send('Hello, World!')
