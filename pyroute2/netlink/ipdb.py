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
import copy
import threading
from socket import AF_INET
from socket import AF_INET6
from pyroute2.netlink.iproute import iproute
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

nla_fields = [i[0] for i in ifinfmsg.nla_map]
nla_fields.append('flags')
nla_fields.append('mask')
nla_fields.append('change')
nla_fields.append('state')


def get_addr_nla(msg):
    nla = None
    if msg['family'] == AF_INET:
        nla = [i[1] for i in msg['attrs']
               if i[0] == 'IFA_LOCAL'][0]
    elif msg['family'] == AF_INET6:
        nla = [i[1] for i in msg['attrs']
               if i[0] == 'IFA_ADDRESS'][0]
    return nla


class upset(set):

    def __init__(self):
        set.__init__(self)
        self.cleanup()
        self.values = {}

    def commit(self):
        for i in self.removed:
            del self.values[i]
        self.cleanup()

    def cleanup(self):
        self.added = set()
        self.removed = set()

    def pop(self, track=True):
        item = set.pop(self)
        if track:
            self.removed.add(item)

    def add(self, key, value=None, track=True):
        if track:
            self.added.add(key)
        self.values[key] = value
        set.add(self, key)

    def remove(self, key, value=None, track=True):
        if track:
            self.removed.add(key)
        # do not remove the value: it will be kept for rollback
        set.remove(self, key)


class dotkeys(dict):

    def __getattribute__(self, key):
        if key in self:
            return self[key]
        else:
            return dict.__getattribute__(self, key)

    def __setattr__(self, key, value):
        if key in self:
            self[key] = value
        else:
            dict.__setattr__(self, key, value)

    def __delattr__(self, key):
        if key in self:
            del self[key]


class interface(dotkeys):
    def __init__(self, dev, ipr=None, parent=None):
        self.ip = ipr
        self.cleanup = ('af_spec',
                        'attrs',
                        'event',
                        'map',
                        'stats',
                        'stats64')
        dev.prefix = 'IFLA_'
        self.parent = parent
        self.last_error = None
        self.fields = [dev.nla2name(i) for i in nla_fields]
        self.__updated = {}
        self.load(dev)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.commit()
        except Exception as e:
            self.last_error = e

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
        self.__updated = {}
        if self.parent is not None:
            self['ipaddr'] = self.parent.ipaddr[self['index']]

    def __setitem__(self, key, value):
        if key in self:
            self.__updated[key] = self[key]
        dotkeys.__setitem__(self, key, value)

    def review(self):
        response = {'ipaddr': [],
                    'attrs': {}}
        for i in self['ipaddr'].added:
            response['ipaddr'].append('+%s/%s' % tuple(i))
        for i in self['ipaddr'].removed:
            response['ipaddr'].append('-%s/%s' % tuple(i))
        for i in tuple(self.__updated.keys()):
            response['attrs'][i] = '%s -> %s' % (self.__updated[i],
                                                 self[i])
        return response

    def rollback(self):
        for i in self['ipaddr'].added:
            self['ipaddr'].remove(i, track=False)
        for i in self['ipaddr'].removed:
            self['ipaddr'].add(i, track=False)
        self['ipaddr'].cleanup()
        for i in tuple(self.__updated.keys()):
            self[i] = self.__updated[i]
            del self.__updated[i]

    def commit(self):
        e = None
        transaction = copy.deepcopy(self.review())
        try:
            # commit IP address changes
            for i in self['ipaddr'].added:
                # add address
                self.ip.addr_add(self['index'], i[0], i[1])
            for i in self['ipaddr'].removed:
                self.ip.addr_del(self['index'], i[0], i[1])
            # commit interface changes
            request = {}
            for key in self.__updated:
                if key in self.fields:
                    request[key] = self[key]
            self.ip.link('set', self['index'], **request)
            # flush IP address changes
            self['ipaddr'].commit()
        except Exception as e:
            # something went wrong: roll the transaction back
            try:
                # remove all added and add all removed
                for i in self['ipaddr'].added:
                    self.ip.addr_del(self['index'], i[0], i[1])
                for i in self['ipaddr'].removed:
                    self.ip.addr_add(self['index'], i[0], i[1])
                # apply old attributes
                request = {}
                for key in tuple(self.__updated.keys()):
                    if key in self.fields:
                        request[key] = self.__updated[key]
                        del self.__updated[key]
                self.ip.link('set', self['index'], **request)
                # rollback IP address tracking
                self['ipaddr'].cleanup()
            except:
                pass
        # re-load interface information
        self.load(self.ip.get_links(self['index'])[0])
        if e is not None:
            e.transaction = transaction
            raise e

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


class ipdb(dotkeys):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.
    '''

    def __init__(self, ipr=None):
        self.ip = ipr or iproute()

        # caches
        self.ipaddr = {}
        self.routes = {}
        self.neighbors = {}

        # load information on startup
        self.update_links(self.ip.get_links())
        self.update_addr(self.ip.get_addr())

        # start monitoring thread
        self.ip.monitor()
        self.ip.mirror()
        self.mthread = threading.Thread(target=self.monitor)
        self.mthread.setDaemon(True)
        self.mthread.start()

    def update_links(self, links):
        for dev in links:
            if dev['index'] not in self.ipaddr:
                self.ipaddr[dev['index']] = upset()
            i = self[dev['index']] = interface(dev, self.ip, self)
            self[i['ifname']] = i

    def update_addr(self, addrs, action='add'):
        for addr in addrs:
            nla = get_addr_nla(addr)
            if nla is not None:
                method = getattr(self.ipaddr[addr['index']], action)
                try:
                    method(key=(nla, addr['prefixlen']),
                           value=addr, track=False)
                except:
                    pass

    def monitor(self):
        while True:
            messages = self.ip.get()
            for msg in messages:
                if msg.get('event', None) == 'RTM_NEWLINK':
                    index = msg['index']
                    if index in self:
                        # get old name
                        old_name = self[index].old_name
                        # load message
                        self[index].load(msg)
                        # check for new name
                        if self[index]['ifname'] != old_name:
                            del self[old_name]
                            self[self[index]['ifname']] = self[index]
                    else:
                        self.update_links([msg])
                elif msg.get('event', None) == 'RTM_DELLINK':
                    del self[self[msg['index']]['ifname']]
                    del self[msg['index']]
                elif msg.get('event', None) == 'RTM_NEWADDR':
                    self.update_addr([msg], 'add')
                elif msg.get('event', None) == 'RTM_DELADDR':
                    self.update_addr([msg], 'remove')
