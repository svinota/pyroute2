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

    def do_error(self, code, reason):
        self.send_error(code, reason)
        self.end_headers()

    def do_POST(self):
        #
        # sanity checks:
        #
        # * path
        if self.path != '/v1/':
            return self.do_error(404, 'url not found')
        # * content length
        if 'Content-Length' not in self.headers:
            return self.do_error(500, 'Content-Length')
        # * content type
        if 'Content-Type' not in self.headers:
            return self.do_error(500, 'Content-Type')
        #

        content_length = int(self.headers['Content-Length'])
        content_type = self.headers['Content-Type']
        data = self.rfile.read(content_length)
        if content_type == 'application/json':
            try:
                request = json.loads(data)
            except ValueError:
                return self.do_error(500, 'Incorrect JSON input')
        else:
            request = {'commands': [data]}

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
