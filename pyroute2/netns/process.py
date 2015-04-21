import types
import atexit
import subprocess
from pyroute2.netns import setns
from pyroute2.config import MpQueue
from pyroute2.config import MpProcess


def _handle(result):
    if result['code'] == 500:
        raise result['data']
    elif result['code'] == 200:
        return result['data']
    else:
        raise TypeError('unsupported return code')


def NSPopenServer(nsname, flags, channel_in, channel_out, argv, kwarg):
    # set netns
    try:
        setns(nsname, flags=flags)
    except Exception as e:
        channel_out.put(e)
        return
    # create the Popen object
    child = subprocess.Popen(*argv, **kwarg)
    # send the API map
    channel_out.put([(x, isinstance(getattr(child, x), types.MethodType))
                     for x in dir(child)])
    while True:
        # synchronous mode
        # 1. get the command from the API
        call = channel_in.get()
        # 2. stop?
        if call['name'] == 'close':
            break
        # 3. run the call
        try:
            attr = getattr(child, call['name'])
            if isinstance(attr, types.MethodType):
                result = attr(*call['argv'], **call['kwarg'])
            else:
                result = attr
            channel_out.put({'code': 200, 'data': result})
        except Exception as e:
            channel_out.put({'code': 500, 'data': e})
    child.wait()


class NSPopen(object):

    def __init__(self, nsname, *argv, **kwarg):
        # create a child
        self.nsname = nsname
        if 'flags' in kwarg:
            self.flags = kwarg.pop('flags')
        else:
            self.flags = 0
        self.channel_out = MpQueue()
        self.channel_in = MpQueue()
        self.server = MpProcess(target=NSPopenServer,
                                args=(self.nsname,
                                      self.flags,
                                      self.channel_out,
                                      self.channel_in,
                                      argv, kwarg))
        # start the child and check the status
        self.server.start()
        response = self.channel_in.get()
        if isinstance(response, Exception):
            self.server.join()
            raise response
        else:
            self.api = dict(response)
            atexit.register(self.close)

    def close(self):
        self.channel_out.put({'name': 'close'})

    def __dir__(self):
        return self.api.keys()

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:

            if self.api.get(key):
                def proxy(*argv, **kwarg):
                    self.channel_out.put({'name': key,
                                          'argv': argv,
                                          'kwarg': kwarg})
                    return _handle(self.channel_in.get())
                return proxy
            else:
                self.channel_out.put({'name': key})
                return _handle(self.channel_in.get())
