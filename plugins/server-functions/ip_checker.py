from flask import Flask
app = Flask('connection-checker')
app.route('/')(lambda: ('', 200))
run = lambda _host, _port: app.run(host=_host, port=_port)
