import traceback
import urlparse
from pyroute2 import IOCore
from pyroute2.iocore import NLT_EXCEPTION


def public(func):
    def reply(self, envelope, msg):
        nonce = envelope['header']['sequence_number']
        src = envelope['src']
        sport = envelope['sport']
        try:
            ret = func(self, msg)
            flags = 0
        except:
            ret = traceback.format_exc()
            flags = NLT_EXCEPTION
        self.push((src, sport), ret, flags, nonce)
        return True

    reply.public = True
    return reply


class Server(IOCore):

    def __init__(self, hosts=None):
        IOCore.__init__(self)
        # start serve
        if type(hosts) not in (tuple, list):
            hosts = [hosts]

        for item in hosts:
            resource = urlparse.urlparse(item)
            self.serve(item)
            self.provide(resource.path)

        # register public methods
        for name in dir(self):
            item = getattr(self, name, None)
            public = getattr(item, 'public', False)

            if public:
                save = name

                def predicate(e, x):
                    return e.get_attr('IPR_ATTR_CNAME') == save

                self.register_callback(item, predicate)

    @public
    def echo(self, msg):
        return "passed: %s" % (msg)


class Client(object):

    def __init__(self, host):
        self.ioc = IOCore()
        resource = urlparse.urlparse(host)
        link, self.addr = self.ioc.connect(host)
        self.port = self.ioc.discover(resource.path, self.addr)

    def __getattribute__(self, key, *argv):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            def call(msg):
                return self.ioc.request(msg,
                                        addr=self.addr,
                                        port=self.port,
                                        cname=key)[0]
            return call
