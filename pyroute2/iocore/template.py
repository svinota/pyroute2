import traceback
import urlparse
import cPickle as pickle
from pyroute2 import IOCore
from pyroute2.iocore import NLT_EXCEPTION


def public(func):
    def reply(self, envelope, msg):
        nonce = envelope['header']['sequence_number']
        src = envelope['src']
        sport = envelope['sport']
        try:
            argv, kwarg = pickle.loads(msg['data'])
            ret = func(self, *argv, **kwarg)
            flags = 0
        except:
            ret = traceback.format_exc()
            flags = NLT_EXCEPTION
        self._ioc.push((src, sport), ret, flags, nonce)
        return True

    reply.public = True
    return reply


class ProxyInterface(object):

    def __init__(self, ioc, host):
        self._ioc = ioc
        path = urlparse.urlparse(host).path
        link, self._addr = self._ioc.connect(host)
        self._port = self._ioc.discover(path, self._addr)

    def __getattribute__(self, key, *argv):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            def call(*argv, **kwarg):
                # pickle argv and kwarg
                msg = pickle.dumps((argv, kwarg))
                return self._ioc.request(msg,
                                         addr=self._addr,
                                         port=self._port,
                                         cname=key)[0]
            return call


def predicate(name):
    return lambda e, x: e.get_attr('IPR_ATTR_CNAME') == name


class Node(object):

    def __init__(self, serve=None):
        self._ioc = IOCore()
        self.namespaces = set()

        # start services
        serve = serve or []
        if type(serve) not in (tuple, list, set):
            serve = [serve]

        for host in serve:
            self.serve(host)

    def register(self, namespace):
        namespace._ioc = self._ioc
        self.namespaces.add(namespace)
        # register public methods
        for name in dir(namespace):
            item = getattr(namespace, name, None)
            public = getattr(item, 'public', False)

            if public:
                self._ioc.register_callback(item, predicate(name))

    def serve(self, host):
        path = urlparse.urlparse(host).path
        self._ioc.serve(host)
        self._ioc.provide(path)

    def connect(self, host):
        return ProxyInterface(self._ioc, host)

    def shutdown(self):
        self._ioc.release()
