import traceback
from pyroute2 import IOCore
from pyroute2.iocore import NLT_EXCEPTION
from pyroute2.iocore import NLT_DGRAM
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse
try:
    import cPickle as pickle
except ImportError:
    import pickle


def public(func):
    def reply(self, envelope, msg):
        nonce = envelope['header']['sequence_number']
        sport = envelope['sport']
        try:
            argv, kwarg = pickle.loads(msg['data'])
            ret = func(self, *argv, **kwarg)
            flags = 0
        except:
            ret = traceback.format_exc()
            flags = NLT_EXCEPTION
        self._ioc.push((0, sport), ret, flags, nonce)
        return True

    reply.public = True
    return reply


class Interface(object):

    def __init__(self, ioc, host, timeout=3):
        self._ioc = ioc
        self._timeout = timeout
        self._res = urlparse.urlparse(host)
        link, self._addr = self._ioc.connect(host)
        self._port = self._ioc.discover(self._res.path, self._addr)


class PushInterface(Interface):

    def __init__(self, ioc, host, dgram, flags=None):
        Interface.__init__(self, ioc, host)
        self.flags = flags
        if (dgram is not None) and (self.flags == NLT_DGRAM):
            self._ioc.connect(dgram)

    def push(self, msg):
        self._ioc.push((self._addr, self._port), msg, self.flags)


class ReqRepInterface(Interface):

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
                                         cname=key,
                                         response_timeout=self._timeout)[0]
            return call


def predicate(name):
    return lambda e, x: e.get_attr('IPR_ATTR_CNAME') == name


class Node(object):

    def __init__(self, serve=None):
        self._ioc = IOCore()
        self.namespaces = set()
        self.resources = set()

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
        # .. _ioc-callbacks:
        for name in dir(namespace):
            item = getattr(namespace, name, None)
            public = getattr(item, 'public', False)

            if public:
                self._ioc.register_callback(item, predicate(name))

    def serve(self, host):
        path = urlparse.urlparse(host).path
        self._ioc.serve(host)
        if path not in self.resources:
            self.resources.add(path)
            self._ioc.provide(path)

    def get(self):
        return self._ioc.get()[0]

    def mirror(self):
        self._ioc.monitor()
        self._ioc.mirror()

    def connect(self, host, timeout=3):
        '''
        Return REQ/REP interface to another node
        '''
        return ReqRepInterface(self._ioc, host, timeout)

    def target(self, host, dgram=None, flags=None):
        '''
        Return PUSH interface to another node
        '''
        return PushInterface(self._ioc, host, dgram, flags)

    def shutdown(self):
        self._ioc.release()
