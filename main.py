# - imports
# general
import os
import general
from colors import *

# server framework
from quart import Quart, websocket, send_file, Response, request, abort, redirect

import uvicorn

from hypercorn.config import Config
import asyncio
from hypercorn.asyncio import serve

from datetime import datetime

# config
import yaml
import secrets

# verbose

# plugins
from plugin_loader.v1 import Loader
import textwrap
from hashlib import shake_128
# from functools import lru_cache
import contextlib

# - constants

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
CWD: str = os.getcwd()
JOIN = os.path.join
METHODS: list[str] = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
# subject to change
SERVER_NAME: str = 'PMgS'
VERSION: str = 'alpha-2.0'
plugin_loader: Loader = Loader(
                     plugin_directory=JOIN(ROOT_DIR, 'plugins'),
                     raise_on_error=False
                 )

# dynamic
PORT: general.DynamicValue = general.DynamicValue(int)
HTML_DIRECTORY: general.DynamicValue = general.DynamicValue(str)
SECRET_KEY: general.DynamicValue = general.DynamicValue(str)
INDEX_FILE: general.DynamicValue = general.DynamicValue(str)
SERVER: general.DynamicValue = general.DynamicValue(str)
SSL_ENABLED: general.DynamicValue = general.DynamicValue(bool)

# still dynamic
ERROR_CODE_HANDLERS: list[int] = []
SSL_CERT_FILE: str = None
SSL_KEY_FILE: str = None
SSL_KEY_PASSWORD: str = None

# - basic server code
print(f'{SERVER_NAME} (version: {VERSION})')

# load config

print(f'Loading {FC.LIGHT_GREEN}config.yml{OPS.RESET}')
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
    print('Loading SSL')
    SSL_CERT_FILE: str = general.DynamicValue(str).check_type(config.get('server.ssl.cert'))
    SSL_CERT_FILE: str = os.path.abspath(general.replace_variables(SSL_CERT_FILE,
                                                                   {'$(ROOT)': ROOT_DIR,
                                                                    '$(CWD)': CWD}))
    if not os.path.exists(SSL_CERT_FILE):
        print('SSL Certificate file could not be found')
        exit(1)
    SSL_KEY_FILE: str = general.DynamicValue(str).check_type(config.get('server.ssl.key'))
    SSL_KEY_FILE: str = os.path.abspath(general.replace_variables(SSL_KEY_FILE,
                                                                  {'$(ROOT)': ROOT_DIR,
                                                                   '$(CWD)': CWD}))
    if not os.path.exists(SSL_KEY_FILE):
        print('SSL Key file could not be found')
        exit(1)
    SSL_KEY_PASSWORD: str = general.DynamicValue(str).check_type(config.get('server.ssl.key-password'))
    if PORT == 80:
        PORT: int = 443

if config.get('server.secret-key') is None:
    config['server.secret-key'] = secrets.token_hex(16)
    print(f'{FC.LIGHT_RED}WARNING!{OPS.RESET} No secret key given, using random key: {config['server.secret-key']}')

SERVER: str = SERVER.check_type(config.get('server.base-server'))

# app init
print(f'running on: {FC.LIGHT_BLUE}quart{OPS.RESET}/{FC.LIGHT_YELLOW}{SERVER}{OPS.RESET}')
app = Quart(__name__,
            static_folder=None, template_folder=None)
app.config['SECRET_KEY'] = SECRET_KEY.check_type(config['server.secret-key'])
# CORS implementation
app.config['CORS_HEADERS'] = 'Content-Type'

print('Loading plugins')
plugin_loader.load_plugins()
plugin_loader.init_plugins()
plugin_loader.load_managers()

#  please don't use this call
plugin_loader.call_id('plugin._attr')

for plugin in plugin_loader.plugins:
    plugin.manager.SERVER_INFORMATION = general.ServerInformation({
        'ROOT_DIR': ROOT_DIR,
        'CWD': CWD,
        'JOIN': JOIN,
        'METHODS': METHODS,
        'SERVER_NAME': SERVER_NAME,
        'LOADER': plugin_loader,
        'PORT': PORT,
        'HTML_DIRECTORY': HTML_DIRECTORY,
        'SECRET_KEY': SECRET_KEY,
        'INDEX_FILE': INDEX_FILE,
        'SERVER': SERVER,
        'SSL_ENABLED': SSL_ENABLED,
        'ERROR_CODE_HANDLERS': ERROR_CODE_HANDLERS,
        'SSL_CERT_FILE': SSL_CERT_FILE,
        'SSL_KEY_FILE': SSL_KEY_FILE,
        'SSL_KEY_PASSWORD': SSL_KEY_PASSWORD,
    })
    plugin.manager.loader = plugin_loader

app.before_request(plugin_loader.get_exposed('check_scheme'))
app.route('/', methods=METHODS, defaults={'file': INDEX_FILE})(
    app.route('/<path:file>', methods=METHODS)(
        plugin_loader.get_exposed('http_index')
    )
)
app.after_request(plugin_loader.get_exposed('server_after_request'))

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


    # print(f'Adding error handler for: {FC.DARK_CYAN}{error_code}{OPS.RESET}')
    ERROR_CODE_HANDLERS.append(error_code)
    app.errorhandler(error_code)(create_error_handler(redirect_to, return_value, return_code))

print(f'Added error handlers for: {', '.join([f'{FC.DARK_CYAN}{x}{OPS.RESET}' for x in ERROR_CODE_HANDLERS])}')

plugin_loader.call_id('plugin.pre-load')

plugin_loader.print_events()
plugin_loader.load_endpoints(app, METHODS, ERROR_CODE_HANDLERS)
plugin_loader.load_sockets(app)

plugin_loader.call_id('plugin.loaded')
plugin_loader.call_id('server.on-load')  # legacy

if __name__ == '__main__':
    nat_addr = plugin_loader.run('get_local_ip')
    public_addr = plugin_loader.run('get_public_ip')

    protocol = 'http' if PORT != 443 else 'https'
    link_port = f':{PORT}' if PORT not in (80, 443) else ''

    print('Checking Public IP connection')
    if public_addr_reachable := plugin_loader.run('check_public_ip', public_addr, PORT):
        print(f'{FC.LIGHT_GREEN}Public IP is reachable{OPS.RESET}')
    else:
        print(f'{FC.LIGHT_RED}Public IP is not reachable{OPS.RESET}')

    print('Starting Webserver, use CTRL+C to exit')
    print(f'Connect to the server using this links:\n'
          f'  {FC.LIGHT_BLUE}Local Machine{OPS.RESET}: {protocol}://127.0.0.1{link_port}/\n'
          f'  {FC.LIGHT_BLUE}Local Network{OPS.RESET}: {protocol}://{nat_addr}{link_port}/')
    if public_addr_reachable:
        print(f'  {FC.LIGHT_BLUE}Public{OPS.RESET}       : {protocol}://{public_addr}{link_port}/')

    plugin_loader.call_id('server.start')

    try:
        match SERVER.lower():
            case 'uvicorn':
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
            case 'hypercorn':
                base_config = Config.from_mapping({
                    'certfile': SSL_CERT_FILE,
                    'keyfile': SSL_KEY_FILE,
                    'keyfile_password': SSL_KEY_PASSWORD,
                    'include_server_header': False,
                    # 'quic_bind': f'0.0.0.0:{PORT}',
                    'bind': f'0.0.0.0:{PORT}',
                    'insecure_bind': f'0.0.0.0:80' if SSL_ENABLED and PORT == 443 else None,
                    'loglevel': 'ERROR',
                })
                asyncio.run(serve(app, base_config))
            case _:
                print(f'Unknown server: {SERVER}')
                plugin_loader.call_id('server.error.server-name')

        plugin_loader.call_id('server.end')
    except FileNotFoundError:
        if SSL_ENABLED:
            print('SSL is enabled but the files could not be found')
            plugin_loader.call_id('server.error.ssl')

    print('Closing WebServer')
