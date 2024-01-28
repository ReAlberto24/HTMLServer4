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
# Gets Nat and Public addresses
import socket
import http.client

# - constants

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()
JOIN = os.path.join
METHODS: list[str] = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

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
def log_response(response: Response):
    general.log_request(raw_request=request, raw_response=response)
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


if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('8.8.8.8', 80))
        nat_addr = s.getsockname()[0]
    del s

    conn = http.client.HTTPSConnection('ipv4.icanhazip.com')
    conn.request('GET', '/')
    public_addr = conn.getresponse().read().decode('utf-8').strip()
    del conn

    protocol = 'http' if PORT != 443 else 'https'
    link_port = f':{PORT}' if PORT not in (80, 443) else ''

    print('Starting WebServer, use CTRL+C to exit')
    print(f'Connect to the server using this links:\n'
          f'  {FC.LIGHT_BLUE}Local Machine{OPS.RESET}: {protocol}://127.0.0.1{link_port}/\n'
          f'  {FC.LIGHT_BLUE}Local Network{OPS.RESET}: {protocol}://{nat_addr}{link_port}/')
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=PORT,
        # disable server builtin logging
        access_log=False, log_level=50,
        ssl_certfile=SSL_CERT_FILE,
        ssl_keyfile=SSL_KEY_FILE,
        ssl_keyfile_password=SSL_KEY_PASSWORD
    )

    print('Closing WebServer')
