# - imports
# general
import os
import general
from colors import *

# server framework
from quart import Quart, websocket, send_file, Response, request, abort
import uvicorn
from datetime import datetime

# config
import yaml
import secrets

# verbose

# plugins
from plugin_loader import Loader
import textwrap
from hashlib import shake_128
from functools import lru_cache
import contextlib

# - constants

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
CWD: str = os.getcwd()
JOIN = os.path.join
METHODS: list[str] = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
# subject to change
SERVER_NAME: str = 'PMgS'
LOADER: Loader = Loader(
                     plugin_directory=JOIN(ROOT_DIR, 'plugins'),
                     raise_on_error=False
                 )

# dynamic
PORT: general.DynamicValue = general.DynamicValue(int)
HTML_DIRECTORY: general.DynamicValue = general.DynamicValue(str)
SECRET_KEY: general.DynamicValue = general.DynamicValue(str)
INDEX_FILE: general.DynamicValue = general.DynamicValue(str)

SSL_ENABLED: general.DynamicValue = general.DynamicValue(bool)

# still dynamic
ERROR_CODE_HANDLERS: list = []
SSL_CERT_FILE: str = None
SSL_KEY_FILE: str = None
SSL_KEY_PASSWORD: str = None

# - basic server code
# load config

with open(JOIN(ROOT_DIR, 'config.yml'), 'r') as conf_file:
    config: dict = yaml.safe_load(conf_file)
    config: dict = general.flatten_dict(config)
del conf_file

PORT: int = PORT.check_type(config.get('server.port'))
HTML_DIRECTORY: str = HTML_DIRECTORY.check_type(config.get('server.html-directory'))
HTML_DIRECTORY: str = os.path.abspath(general.replace_variables(HTML_DIRECTORY,
                                                                {'$(ROOT)': ROOT_DIR,
                                                                 '$(CWD)': CWD}))
INDEX_FILE: str = INDEX_FILE.check_type(config.get('server.index-file'))
SSL_ENABLED: bool = SSL_ENABLED.check_type(config.get('server.ssl.enabled'))
if SSL_ENABLED:
    SSL_CERT_FILE: str = general.DynamicValue(str).check_type(config.get('server.ssl.cert'))
    SSL_CERT_FILE: str = os.path.abspath(general.replace_variables(SSL_CERT_FILE,
                                                                   {'$(ROOT)': ROOT_DIR,
                                                                    '$(CWD)': CWD}))
    SSL_KEY_FILE: str = general.DynamicValue(str).check_type(config.get('server.ssl.key'))
    SSL_KEY_FILE: str = os.path.abspath(general.replace_variables(SSL_KEY_FILE,
                                                                  {'$(ROOT)': ROOT_DIR,
                                                                   '$(CWD)': CWD}))
    SSL_KEY_PASSWORD: str = general.DynamicValue(str).check_type(config.get('server.ssl.key-password'))
    if PORT == 80:
        PORT = 443

if config.get('server.secret-key') is None:
    config['server.secret-key'] = secrets.token_hex(16)
    print(f'{FC.LIGHT_RED}WARNING!{OPS.RESET} No secret key given, using random key: {config['server.secret-key']}')

# app init

app = Quart(__name__,
            static_folder=None, template_folder=None)
app.config['SECRET_KEY'] = SECRET_KEY.check_type(config['server.secret-key'])
# CORS implementation
app.config['CORS_HEADERS'] = 'Content-Type'


@app.route('/', methods=METHODS)
@app.route('/<path:file>', methods=METHODS)
async def http_index(file: str = INDEX_FILE):
    retrn = LOADER.call_id('server.request', request)
    if retrn is not None:
        return retrn
    f = general.resolve_directory_path(JOIN(HTML_DIRECTORY, *file.split('/')))
    if general.is_in_directory(HTML_DIRECTORY, f):
        if os.path.isdir(f) and os.path.exists(JOIN(f, INDEX_FILE)):
            return await send_file(JOIN(f, INDEX_FILE)), 200
        elif os.path.exists(f):
            # Check if the file size is greater than 1MB
            if os.path.getsize(f) > 1000000:
                return await send_file(f, conditional=True), 206
            elif modified_client := request.headers.get('If-Modified-Since'):
                client_time = datetime.strptime(modified_client, '%a, %d %b %Y %H:%M:%S %Z')
                if client_time <= datetime.fromtimestamp(os.path.getmtime(f)):
                    return '', 304
            return await send_file(f), 200
    abort(404)


@app.after_request
def server_after_request(response: Response):
    general.log_request(raw_request=request, raw_response=response)
    response.headers['Server'] = SERVER_NAME
    return response


print('Loading Error Handlers')
for handler_file in os.listdir(JOIN(ROOT_DIR, 'error-handlers')):
    handler_path = JOIN(ROOT_DIR, 'error-handlers', handler_file)

    with open(handler_path, 'r') as f_handler:
        handler_data = yaml.safe_load(f_handler)
    del f_handler

    code_from_name = int(os.path.basename(handler_path).rsplit('.', 1)[0])

    error_code = handler_data.get('error-code', code_from_name)
    redirect_to = handler_data.get('redirect-to', None)
    return_value = handler_data.get('return', None)
    return_code = handler_data.get('return-code', code_from_name)


    def create_error_handler(_redirect_to, _return_value, _return_code):
        def error_handler(err):
            if _return_value is None:
                return send_file(JOIN(HTML_DIRECTORY, _redirect_to))
            return _return_value, _return_code

        return error_handler


    print(f'Adding error handler for: {FC.DARK_CYAN}{error_code}{OPS.RESET}')
    ERROR_CODE_HANDLERS.append(error_code)
    app.errorhandler(error_code)(create_error_handler(redirect_to, return_value, return_code))


print('Loading plugins')
LOADER.load_plugins()
LOADER.init_plugins()
LOADER.load_managers()

LOADER.call_id('plugin.pre-load')

all_endpoints = [endpoint for plugin in LOADER.plugins for endpoint in plugin.manager._endpoints]
longest_endpoint = len(max(all_endpoints, key=len)) if all_endpoints else 0

for plugin in LOADER.plugins:
    print(f'{FC.LIGHT_MAGENTA}{plugin.configuration.id_}{OPS.RESET} events: ' +
          ', '.join([f'{FC.DARK_YELLOW}{i}{OPS.RESET}' for i in plugin.manager._functions.keys()]))

    # hackery
    with contextlib.redirect_stdout(plugin.stdout_buffer):
        plugin.manager._functions.get('plugin.loading.pre-endpoints', lambda: None)()

    for endpoint in plugin.manager._endpoints:
        def create_plugin():
            plugin_id = 'f' + shake_128(plugin.configuration.id_.encode()).hexdigest(8)
            function_identifier = secrets.token_hex(4)
            name = f'{plugin_id}_c{function_identifier}'
            lcls = {}
            glbls = {
                'LOADER': LOADER,
                'request': request,
                'plugin_': plugin,
                'ERROR_CODE_HANDLERS': ERROR_CODE_HANDLERS,
                'abort': abort,
                'FC': FC,
                'OPS': OPS,
            }
            exec(textwrap.dedent(f'''
                async def {name}(*_args, **_kwargs):
                    retrn = LOADER.call_id('server.request', request)
                    if retrn is not None: return retrn
                    try:
                        data, _return_code = plugin_.manager.call_endpoint(
                            endpoint='{endpoint}', *_args, **_kwargs, request=request
                        )
                    except (ValueError, TypeError):
                        raise ValueError("Endpoint \\"{endpoint}\\" in {plugin.configuration.id_}"
                                         " doesn't return 2 values")
                    if _return_code in ERROR_CODE_HANDLERS: abort(_return_code)
                    return data, _return_code
                '''), glbls, lcls)
            return lcls[name]
        new_function = create_plugin()
        doc = plugin.manager._endpoints[endpoint]['func'].__doc__
        doc = doc if doc is not None else 'No docs included'
        doc = doc.replace('\n', '\n         ')
        print(f'Adding endpoint       : {FC.DARK_YELLOW}{endpoint: <{longest_endpoint + 3}}{OPS.RESET} | '
              f'{plugin.configuration.id_} | {new_function.__name__}\n - docs: {doc}')
        app.route(endpoint, methods=METHODS)(new_function)

    # again
    with contextlib.redirect_stdout(plugin.stdout_buffer):
        plugin.manager._functions.get('plugin.loading.post-endpoints', lambda: None)()

    # and again
    with contextlib.redirect_stdout(plugin.stdout_buffer):
        plugin.manager._functions.get('plugin.loading.pre-sockets', lambda: None)()

    for endpoint in plugin.manager._sockets:
        def create_plugin():
            plugin_id = 'f' + shake_128(plugin.configuration.id_.encode()).hexdigest(8)
            function_identifier = secrets.token_hex(4)
            name = f'{plugin_id}_s{function_identifier}'
            lcls = {}
            glbls = {
                'LOADER': LOADER,
                'request': request,
                'plugin_': plugin,
                'ERROR_CODE_HANDLERS': ERROR_CODE_HANDLERS,
                'abort': abort,
                'FC': FC,
                'OPS': OPS,
                'websocket': websocket,
                'log_request': general.log_request,
            }
            exec(textwrap.dedent(f'''
                async def {name}(*_args, **_kwargs):
                    await LOADER.call_id('server.socket', websocket)
                    log_request(method='SOCKET',
                                endpoint=websocket.full_path if len(websocket.args) > 0 else websocket.path,
                                return_code=None,
                                custom_color=FC.DARK_GREEN)
                    await plugin_.manager.socket(endpoint='{endpoint}', *_args, **_kwargs, ws=websocket)
                '''), glbls, lcls)
            return lcls[name]


        new_function = create_plugin()
        doc = plugin.manager._sockets[endpoint].__doc__
        doc = doc if doc is not None else 'No docs included'
        doc = doc.replace('\n', '\n         ')
        print(f'Adding socket endpoint: {FC.DARK_YELLOW}{endpoint: <{longest_endpoint + 3}}{OPS.RESET} | '
              f'{plugin.configuration.id_} | {new_function.__name__}\n - {doc}')
        app.websocket(endpoint)(new_function)

    # just do it
    with contextlib.redirect_stdout(plugin.stdout_buffer):
        plugin.manager._functions.get('plugin.loading.post-sockets', lambda: None)()


LOADER.call_id('plugin.loaded')


if __name__ == '__main__':
    nat_addr = LOADER.run('get_local_ip')

    protocol = 'http' if PORT != 443 else 'https'
    link_port = f':{PORT}' if PORT not in (80, 443) else ''

    print('Starting WebServer, use CTRL+C to exit')
    print(f'Connect to the server using this links:\n'
          f'  {FC.LIGHT_BLUE}Local Machine{OPS.RESET}: {protocol}://127.0.0.1{link_port}/\n'
          f'  {FC.LIGHT_BLUE}Local Network{OPS.RESET}: {protocol}://{nat_addr}{link_port}/')

    LOADER.call_id('server.start')

    uvicorn.run(
        app,
        host='0.0.0.0',
        port=PORT,
        server_header=False,
        # disable server builtin logging
        access_log=False, log_level=50,
        ssl_certfile=SSL_CERT_FILE,
        ssl_keyfile=SSL_KEY_FILE,
        ssl_keyfile_password=SSL_KEY_PASSWORD
    )

    LOADER.call_id('server.end')

    print('Closing WebServer')
