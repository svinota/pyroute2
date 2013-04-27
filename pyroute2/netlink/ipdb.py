'''
Experimental IP database module. Please, do not use it
unless you understand what are you doing.

Quick start:
    from pyroute2.netlink.ipdb import ipdb
    ip = ipdb()
    ip['eth0'].down()
    ip['eth0']['address'] = '00:11:22:33:44:55'
    ip['eth0']['ifname'] = 'bala'
    ip['eth0']['txqlen'] = 2000
    ip['eth0'].commit()
    ip['bala'].up()
'''
import threading

from pyroute2.netlink.iproute import iproute
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

nla_fields = [i[0] for i in ifinfmsg.nla_map]
nla_fields.append('flags')
nla_fields.append('mask')
nla_fields.append('change')
nla_fields.append('state')


class dotkeys(dict):

    def __getattribute__(self, key):
        if key in self:
            return self[key]
        else:
            return dict.__getattribute__(self, key)

    def __setattr__(self, key, value):
        print(type(self), key, value)
        if key[-10:] != '__reserved':
            if key not in self.__reserved:
                self[key] = value
                return
        dict.__setattr__(self, key, value)

    def __delattr__(self, key):
        if key in self:
            del self[key]


class interface(dict):
    def __init__(self, dev, ipr=None):
        self.ip = ipr
        self.cleanup = ('af_spec',
                        'attrs',
                        'event',
                        'map',
                        'stats',
                        'stats64')
        dev.prefix = 'IFLA_'
        self.fields = [dev.nla2name(i) for i in nla_fields]
        self.__updated = set()
        self.load(dev)

    def load(self, dev):
        dev.prefix = 'IFLA_'
        # invalidate old info
        for key in tuple(self.keys()):
            del self[key]
        # load new info
        self.update(dev)
        self.__attrs = set()
        for (name, value) in dev['attrs']:
            norm = dev.nla2name(name)
            self.__attrs.add(norm)
            self[norm] = value
        for item in self.cleanup:
            if item in self:
                del self[item]
        self.old_name = self['ifname']
        self.__updated = set()

    def __setitem__(self, key, value):
        self.__updated.add(key)
        dotkeys.__setitem__(self, key, value)

    def commit(self):
        request = {}
        for key in self.__updated:
            if key in self.fields:
                request[key] = self[key]
        response = self.ip.link('set', self['index'], **request)
        self.load(self.ip.get_links(self['index'])[0])
        return response

    def up(self):
        self.ip.link('set', self['index'], state='up')

    def down(self):
        self.saved_flags = self['flags']
        self.ip.link('set', self['index'], state='down')

    def restore(self):
        self.ip.link('set', self['index'],
                     flags=self.saved_flags, mask=0xffff)

    def rename(self, name):
        self.down()
        self.ip.link('set', self['index'], ifname=name)
        self.restore()

    def remove(self):
        self.ip.link('delete', self['index'])


class ipdb(dict):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.
    '''

    def __init__(self, ipr=None):
        self.ip = ipr or iproute()
        self.lock = threading.Lock()

        # start monitoring thread
        self.ip.monitor()
        self.mthread = threading.Thread(target=self.monitor)
        self.mthread.setDaemon(True)
        self.mthread.start()

        # load information on startup
        self.update(self.ip.get_links())

    def update(self, links):
        with self.lock:
            for dev in links:
                i = self[dev['index']] = interface(dev, self.ip)
                self[i['ifname']] = i

    def monitor(self):
        while True:
            messages = self.ip.get()
            for msg in messages:
                if msg['event'] == 'RTM_NEWLINK':
                    index = msg['index']
                    # get old name
                    old_name = self[index].old_name
                    # load message
                    self[index].load(msg)
                    # check for new name
                    if self[index]['ifname'] != old_name:
                        del self[old_name]
                        self[self[index]['ifname']] = self[index]
                elif msg['event'] == 'RTM_DELLINK':
                    del self[msg['index']['ifname']]
                    del self[msg['index']]
