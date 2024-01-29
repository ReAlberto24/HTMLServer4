from plugin_manager import Manager

# Gets Nat and Public addresses
import socket
import http.client

# CGI and Custom templates
import os
from quart import Response, make_response
import sys
from bs4 import BeautifulSoup
import textwrap
import subprocess
import io
from email.parser import BytesParser

BASE_PHP_PATH = os.path.join(os.path.dirname(__file__), 'php')
PHP_EXECUTABLE = os.path.join(BASE_PHP_PATH, 'php.exe')
PYTHON_EXECUTABLE = sys.executable
manager = Manager()


@manager.expose
def get_public_ip() -> str:
    conn = http.client.HTTPSConnection('ipv4.icanhazip.com')
    conn.request('GET', '/')
    public_addr = conn.getresponse().read().decode('utf-8').strip()
    del conn
    return public_addr


@manager.expose
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


@manager.on('server.request._cgi')
def cgi_request(f: str) -> Response | tuple[str, int] | None:
    global PHP_EXECUTABLE, PYTHON_EXECUTABLE
    match f.rsplit('.', 1)[1]:
        case 'php':
            if not os.path.exists(PHP_EXECUTABLE):
                return
            proc = subprocess.run([PHP_EXECUTABLE, '-q', f],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL)
            # print(proc.stdout.decode(), proc.returncode)
            # data = proc.stdout
            # response = http.client.HTTPResponse(FakeSocket(data))
            # response.begin()
            # headers = parse_http_headers(response.headers.as_string())
            # return Response(response.read(len(data)), response.status, dict(headers))
            return proc.stdout.decode(), 200
        case 'py' | 'pyw' | 'py3':
            if not os.path.exists(PYTHON_EXECUTABLE):
                return
            proc = subprocess.run([PYTHON_EXECUTABLE, f],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL)
            return proc.stdout.decode(), 200


@manager.expose
def parse_pmgs_template(file: str = None) -> str:
    # file as file_data
    if file is None:
        return ''

    bs_file = BeautifulSoup(file, features='html.parser')
    for p_tag in bs_file.find_all('python'):
        python_code = textwrap.dedent(str(p_tag)[8:-9])
        proc = subprocess.run([sys.executable, '-c', python_code],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL)
        p_tag.replace_with(proc.stdout.decode())
    return str(bs_file)
