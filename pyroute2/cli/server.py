import json
from pyroute2 import NDB
from pyroute2.cli.session import Session

try:
    from BaseHTTPServer import HTTPServer as HTTPServer
    from BaseHTTPServer import BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer as HTTPServer
    from http.server import BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        assert self.path == '/v1/'
        clen = int(self.headers['Content-Length'])
        request = json.loads(self.rfile.read(clen))
        session = Session(ndb=self.server.ndb, stdout=self.wfile)
        self.send_response(200)
        self.end_headers()
        for cmd in request['commands']:
            session.handle(cmd)


class Server(HTTPServer):

    def __init__(self,
                 address='localhost',
                 port=8080,
                 debug=None,
                 sources=None):
        self.sessions = {}
        self.ndb = NDB(debug=debug, sources=sources)
        self.ndb.config = {'show_format': 'json'}
        HTTPServer.__init__(self, (address, port), Handler)
