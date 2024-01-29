from plugin_manager import Manager

# Gets Nat and Public addresses
import socket
import http.client

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