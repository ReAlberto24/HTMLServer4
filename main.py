# - imports
# general
import os
import general
from colors import *

# server framework
from quart import Quart, websocket
import uvicorn

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
    return file, 200


if __name__ == '__main__':
    print(HTML_DIRECTORY)
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=PORT,
        # disable server builtin logging
        access_log=False, log_level=50
    )
