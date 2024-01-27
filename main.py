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

# - constants

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()
JOIN = os.path.join
METHODS: list[str] = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

PORT: general.DynamicValue = general.DynamicValue(int)
HTML_DIRECTORY: general.DynamicValue = general.DynamicValue(str)
SECRET_KEY: general.DynamicValue = general.DynamicValue(str)

# still dynamic
ERROR_CODE_HANDLERS: list = []

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
async def http_index(file: str = 'index.html'):
    f = general.resolve_directory_path(JOIN(HTML_DIRECTORY, *file.split('/')))
    if general.is_in_directory(HTML_DIRECTORY, f):
        if os.path.isdir(f) and os.path.exists(JOIN(f, 'index.html')):
            return await send_file(JOIN(f, 'index.html')), 200
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

    error_code = handler_data.get('error-code')
    redirect_to = handler_data.get('redirect-to')
    return_value = handler_data.get('return')
    return_code = handler_data.get('return-code')


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
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=PORT,
        # disable server builtin logging
        access_log=False, log_level=50
    )
