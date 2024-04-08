import os
import sys
import time

sys.path.append(os.path.dirname(__file__))

from plugin_manager import Manager

# Gets Nat and Public addresses
import socket
import http.client
import requests
import subprocess

# CGI and Custom templates
from quart import Response, make_response, Request, Quart, request, redirect
from bs4 import BeautifulSoup
import textwrap
import subprocess
import io
from functools import lru_cache
import platform
from multiprocessing import Process

BASE_PHP_PATH = os.path.join(os.path.dirname(__file__), 'php')
PHP_EXECUTABLE = os.path.join(BASE_PHP_PATH, 'php-cgi.exe')
PYTHON_EXECUTABLE = sys.executable
manager = Manager()
upgrade_proc = None


@manager.on('server.start')
def on_start():
    global upgrade_proc
    if manager.SERVER_INFORMATION.SERVER.lower() == 'hypercorn':
        # integrated
        return

    if manager.SERVER_INFORMATION.SSL_ENABLED and manager.SERVER_INFORMATION.PORT == 443:
        print('Starting upgrade-conn process')
    else:
        return

    upgrade_proc = subprocess.Popen([sys.executable, '-c',
                                     "from quart import Quart, request, redirect\n"
                                     "upgrade_server = Quart('HTMLServer4.UPGRADE-CONN')\n"
                                     "@upgrade_server.route('/', methods=['GET'])\n"
                                     "@upgrade_server.route('/<path:file>', methods=['GET'])\n"
                                     "async def upgrade_conn():\n"
                                     "    if not request.is_secure:\n"
                                     "        url = request.url.replace('http://', 'https://', 1)\n"
                                     "        return redirect(url, code=301)\n"
                                     "upgrade_server.run(host='0.0.0.0', port=80)"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL)


@manager.on('server.end')
def on_exit():
    global upgrade_proc
    if upgrade_proc:
        try:
            upgrade_proc.kill()
        except AttributeError:
            pass


@manager.expose(name='get_public_ip')
@lru_cache()
def get_public_ip() -> str:
    conn = http.client.HTTPSConnection('ipv4.icanhazip.com')
    conn.request('GET', '/')
    public_addr = conn.getresponse().read().decode('utf-8').strip()
    del conn
    return public_addr


@manager.expose(name='get_local_ip')
@lru_cache()
def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('8.8.8.8', 80))
        nat_addr = s.getsockname()[0]
    del s
    return nat_addr


class FakeSocket:
    def __init__(self, response_bytes):
        self._file = io.BytesIO(response_bytes)

    def makefile(self, *args, **kwargs):
        return self._file


def parse_http_headers(header_string):
    headers_dict = {}
    header_lines = header_string.split('\n')
    for line in header_lines:
        if line.strip() == '':
            continue
        header, value = line.split(':', 1)
        header = header.strip()
        value = value.strip()
        headers_dict[header] = value
    return headers_dict


# print(proc.stdout.decode(), proc.returncode)
# data = proc.stdout
# response = http.client.HTTPResponse(FakeSocket(data))
# response.begin()
# headers = parse_http_headers(response.headers.as_string())
# return Response(response.read(len(data)), response.status, dict(headers))


@manager.on('server.request._cgi')
def cgi_request(raw_path: str, f: str, request: Request) -> Response | tuple[str, int] | None:
    global PHP_EXECUTABLE, PYTHON_EXECUTABLE
    if f.rsplit('.', 1)[1] in ('php', 'py', 'pyw', 'py3'):
        env = {'SCRIPT_URL': request.path,
               'SCRIPT_URI': request.base_url,
               'HTTP_HOST': request.host,
               'HTTP_CONNECTION': request.headers['Connection'],
               'HTTP_DNT': request.headers['DNT'],
               'HTTP_UPGRADE_INSECURE_REQUESTS': request.headers['Upgrade-Insecure-Requests'],
               'HTTP_USER_AGENT': request.user_agent.string,
               'HTTP_ACCEPT': request.headers['Accept'],
               'HTTP_ACCEPT_ENCODING': request.headers['Accept-Encoding'],
               'HTTP_ACCEPT_LANGUAGE': request.headers['Accept-Language'],
               'PATH': '',
               'SERVER_SIGNATURE': f'PMgS (Python {platform.python_version()}) on {platform.platform(aliased=True)}',
               'SERVER_SOFTWARE': 'PMgS',
               'SERVER_NAME': get_public_ip(),
               'SERVER_ADDR': get_public_ip(),
               'SERVER_PORT': str(manager.SERVER_INFORMATION['PORT']),
               'REMOTE_ADDR': request.remote_addr,
               'DOCUMENT_ROOT': manager.SERVER_INFORMATION['HTML_DIRECTORY'],
               'REQUEST_SCHEME': request.scheme,
               # CONTEXT_PREFIX
               'CONTEXT_DOCUMENT_ROOT': manager.SERVER_INFORMATION['HTML_DIRECTORY'],
               # SERVER_ADMIN
               'SCRIPT_FILENAME': f,
               # REMOTE_PORT
               'GATEWAY_INTERFACE': 'CGI/1.1',
               'SERVER_PROTOCOL': 'HTTP/1.1',
               'REQUEST_METHOD': request.method,
               'QUERY_STRING': request.query_string.decode(),
               'REQUEST_URI': request.full_path,
               'SCRIPT_NAME': raw_path,
               'PHP_SELF': raw_path,
               # what
               'REDIRECT_STATUS': '0'
               }
        match f.rsplit('.', 1)[1]:
            case 'php':
                if not os.path.exists(PHP_EXECUTABLE):
                    return
                proc = subprocess.run([PHP_EXECUTABLE, '--no-header', f],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      stdin=subprocess.DEVNULL,
                                      cwd=os.path.dirname(f),
                                      env=env)
                # goddamn header
                return proc.stdout.decode()[64:], 200
            case 'py' | 'pyw' | 'py3':
                if not os.path.exists(PYTHON_EXECUTABLE):
                    return
                proc = subprocess.run([PYTHON_EXECUTABLE, f],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      stdin=subprocess.DEVNULL,
                                      cwd=os.path.dirname(f),
                                      env=env)
                return proc.stdout.decode(), 200
    return '', 500


@manager.expose
def parse_pmgs_template(file: str = None) -> str:
    # file as file_data
    if file is None:
        return ''

    # lxml
    bs_file = BeautifulSoup(file, features='html.parser')
    for p_tag in bs_file.find_all('python'):
        python_code = textwrap.dedent(str(p_tag)[8:-9])
        proc = subprocess.run([sys.executable, '-c', python_code],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL)
        p_tag.replace_with(proc.stdout.decode())
    return str(bs_file)


@manager.expose(name='check_public_ip')
@lru_cache()
def check_public_ip(ip: str, port: int) -> bool:
    process = subprocess.run([sys.executable, '-c',
                              f'import sys\n'
                              f'sys.path = {sys.path}\n'
                              f'from ip_checker import run\n'
                              f'from threading import Thread\n'
                              f'import requests\n'
                              f'def is_server_up(server_url, timeout=3, max_retries=2):\n'
                              f'    for _ in range(max_retries):\n'
                              f'        try:\n'
                              f'            response = requests.get(server_url, timeout=timeout)\n'
                              f'            return response.status_code == 200\n'
                              f'        except (requests.ConnectionError, requests.Timeout):\n'
                              f'            continue\n'
                              f'    return False\n'
                              f'Thread(target=run, args=("0.0.0.0", {port}), daemon=True).start()\n'
                              f'if is_server_up("http://{ip}:{port}"):\n'
                              f'    exit(0)\n'
                              f'exit(1)'],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
    return process.returncode == 0
