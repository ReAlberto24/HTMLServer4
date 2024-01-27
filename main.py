# - imports
# general
import os

# server framework
from quart import Quart, websocket
import uvicorn

# config
import yaml

# - constants

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
JOIN = os.path.join

# - basic server code
# load config

with open(JOIN(ROOT_DIR, 'config.yml'), 'r') as file:
    config = yaml.safe_load(file)

app = Quart(__name__,
            static_folder=None, template_folder=None)


@app.route('/')
async def homepage():
    return '', 200


if __name__ == '__main__':
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=8000,
        # disable server builtin logging
        access_log=False, log_level=50
    )
