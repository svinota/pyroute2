import os
import errno
import tempfile
from pyroute2 import netns
from pyroute2 import Inotify
from pyroute2 import IPRoute
from pyroute2.netlink.rtnl import RTM_NEWNETNS
from pyroute2.netlink.rtnl import RTM_DELNETNS
from pyroute2.netlink.rtnl.nsinfmsg import nsinfmsg
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.exceptions import SkipInode


class NetNSManager(Inotify):

    def __init__(self, libc=None, path=None):
        path = set(path or [])
        self.control_dir = tempfile.mkdtemp()
        super(NetNSManager, self).__init__(libc, path)
        if not self.path:
            for d in ['/var/run/netns', '/var/run/docker/netns']:
                try:
                    self.register_path(d)
                except OSError:
                    pass
        self.register_path(self.control_dir)
        self.ipr = IPRoute()
        self.registry = {}
        self.update()

    def update(self):
        self.ipr.netns_path = self.path
        for info in self.ipr.get_netns_info():
            self.registry[info.get_attr('NSINFO_PATH')] = info

    def get(self):
        for msg in super(NetNSManager, self).get():
            if msg['path'] == self.control_dir:
                error = NetlinkError(errno.ECONNRESET)
                raise error
            path = '{path}/{name}'.format(**msg)
            info = nsinfmsg()
            info['header']['error'] = None
            if path not in self.registry:
                self.update()
            if path in self.registry:
                info.load(self.registry[path])
            else:
                info['attrs'] = [('NSINFO_PATH', path)]
            del info['value']
            if msg['mask'] & 0x200:
                info['header']['type'] = RTM_DELNETNS
                info['event'] = 'RTM_DELNETNS'
            elif not msg['mask'] & 0x100:
                continue
            yield info

    def close(self):
        with open('%s/close' % self.control_dir, 'w'):
            pass
        super(NetNSManager, self).close()
        os.remove('%s/close' % self.control_dir)
        os.rmdir(self.control_dir)

    def create(self, path):
        netnspath = netns._get_netnspath(path)
        try:
            netns.create(netnspath, self.libc)
        except OSError as e:
            raise NetlinkError(e.errno)
        info = self.ipr._dump_one_ns(netnspath, set())
        info['header']['type'] = RTM_NEWNETNS
        info['event'] = 'RTM_NEWNETNS'
        del info['value']
        return info,

    def remove(self, path):
        netnspath = netns._get_netnspath(path)
        infp = None
        try:
            info = self.ipr._dump_one_ns(netnspath, set())
        except SkipInode:
            raise NetlinkError(errno.EEXIST)
        info['header']['type'] = RTM_DELNETNS
        info['event'] = 'RTM_DELNETNS'
        del info['value']
        try:
            netns.remove(netnspath, self.libc)
        except OSError as e:
            raise NetlinkError(e.errno)
        return info,

    def netns(self, cmd, *argv, **kwarg):
        path = kwarg.get('path', kwarg.get('NSINFO_PATH'))
        if path is None:
            raise ValueError('netns spec is required')
        netnspath = netns._get_netnspath(path)
        if cmd == 'add':
            return self.create(netnspath)
        elif cmd == 'del':
            return self.remove(netnspath)
        elif cmd not in ('get', 'set'):
            raise ValueError('method not supported')
        for item in self.dump():
            if item.get_attr('NSINFO_PATH') == netnspath:
                return (item, )
        return tuple()

    def dump(self):
        return self.ipr.get_netns_info()
