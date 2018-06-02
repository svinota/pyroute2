import atexit
import logging
import subprocess
from pyroute2.remote import Transport
from pyroute2.remote import RemoteSocket
from pyroute2.iproute import RTNL_API
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl

log = logging.getLogger(__name__)


class ShellIPR(RTNL_API, RemoteSocket):

    def __init__(self, target):

        self.target = target
        cmd = '%s python -m pyroute2.remote' % target
        self.shell = subprocess.Popen(cmd.split(),
                                      bufsize=0,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)
        self.trnsp_in = Transport(self.shell.stdout)
        self.trnsp_out = Transport(self.shell.stdin)

        try:
            super(ShellIPR, self).__init__()
        except Exception:
            self.close()
            raise
        atexit.register(self.close)
        self.marshal = MarshalRtnl()

    def clone(self):
        return type(self)(self.target)

    def _cleanup_atexit(self):
        if hasattr(atexit, 'unregister'):
            atexit.unregister(self.close)
        else:
            try:
                atexit._exithandlers.remove((self.close, (), {}))
            except ValueError:
                pass

    def close(self):
        self._cleanup_atexit()
        try:
            super(ShellIPR, self).close()
        except:
            # something went wrong, force server shutdown
            try:
                self.trnsp_out.send({'stage': 'shutdown'})
            except Exception:
                pass
            log.error('forced shutdown procedure, clean up netns manually')
        # force cleanup command channels
        for close in (self.trnsp_in.close, self.trnsp_out.close):
            try:
                close()
            except Exception:
                pass  # Maybe already closed in remote.Client.close

        self.shell.kill()
        self.shell.wait()

    def post_init(self):
        pass
