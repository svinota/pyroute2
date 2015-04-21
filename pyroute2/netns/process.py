import atexit
import subprocess
from pyroute2.netns import setns
from pyroute2.config import MpQueue
from pyroute2.config import MpProcess


def NSPopenServer(nsname, flags, channel_in, channel_out, argv, kwarg):
    # set netns
    try:
        setns(nsname, flags=flags)
    except Exception as e:
        channel_out.put(e)
        return
    channel_out.put(None)
    # create the Popen object
    p = subprocess.Popen(*argv, **kwarg)
    while True:
        # synchronous mode
        # 1. get the command from the API
        call = channel_in.get()
        # 2. stop?
        if call['name'] == 'close':
            return
        # 3. run the call
        try:
            method = getattr(p, call['name'])
            result = method(*call['argv'], **call['kwarg'])
            channel_out.put({'code': 200, 'data': result})
        except Exception as e:
            channel_out.put({'code': 500, 'data': e})


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
        error = self.channel_in.get()
        if error is not None:
            self.server.join()
            raise error
        else:
            atexit.register(self.close)

    def close(self):
        self.channel_out.put({'name': 'close'})

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:

            def proxy(*argv, **kwarg):
                self.channel_out.put({'name': key,
                                      'argv': argv,
                                      'kwarg': kwarg})
                result = self.channel_in.get()
                if result['code'] == 500:
                    raise result['data']
                elif result['code'] == 200:
                    return result['data']
                else:
                    raise TypeError('unsupported return code')
            return proxy
