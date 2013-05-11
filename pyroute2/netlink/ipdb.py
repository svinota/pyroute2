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
    '''
    Objects of this class represent network interface and
    all related objects:
        * addresses
        * (todo) neighbors
        * (todo) routes

    Interfaces provide transactional model and can act as
    context managers. Any attribute change implicitly
    starts a transaction. The transaction can be managed
    with three methods:
        * review() -- review changes
        * rollback() -- drop all the changes
        * commit() -- try to apply changes

    If anything will go wrong during transaction commit,
    it will be rolled back authomatically and an
    exception will be raised. Failed transaction review
    will be attached to the exception.
    '''
    def __init__(self, dev, ipr=None, parent=None):
        '''
        One can use interface objects standalone as
        well as in connection with ipdb object. Standalone
        usage, though, is discouraged.

        Parameters:
            * dev -- RTM_NEWLINK message
            * ipd -- iproute() reference
            * parent -- ipdb() reference
        '''
        self.ip = ipr
        self.cleanup = ('header',
                        'af_spec',
                        'attrs',
                        'event',
                        'map',
                        'stats',
                        'stats64')
        dev.prefix = 'IFLA_'
        self.last_error = None
        self._parent = parent
        self._fields = [dev.nla2name(i) for i in nla_fields]
        self._updated = {}
        self._slaves = dotkeys()
        self.load(dev)

    def __hash__(self):
        return self['index']

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.commit()
        except Exception as e:
            self.last_error = e

    @property
    def if_master(self):
        return self._parent[self['master']]

    @property
    def if_slaves(self):
        return self._slaves

    def load(self, dev):
        '''
        Update the interface info from RTM_NEWLINK message.
        '''
        dev.prefix = 'IFLA_'
        self.update(dev)
        self._attrs = set()
        for (name, value) in dev['attrs']:
            norm = dev.nla2name(name)
            self._attrs.add(norm)
            self[norm] = value
        for item in self.cleanup:
            if item in self:
                del self[item]
        # save ifname for transaction
        self.old_name = self['ifname']
        self._updated = {}
        # the rest is possible only when interface
        # is used in IPDB, not standalone
        if self._parent is not None:
            # load IP addresses from IPDB
            self['ipaddr'] = self._parent.ipaddr[self['index']]

    def __setitem__(self, key, value):
        if key in self:
            self._updated[key] = self[key]
        dotkeys.__setitem__(self, key, value)

    def review(self):
        '''
        Review the changes that are not commited yet. Output
        format can be changed later.
        '''
        response = {'ipaddr': [],
                    'attrs': {}}
        for i in self['ipaddr'].added:
            response['ipaddr'].append('+%s/%s' % tuple(i))
        for i in self['ipaddr'].removed:
            response['ipaddr'].append('-%s/%s' % tuple(i))
        for i in tuple(self._updated.keys()):
            response['attrs'][i] = '%s -> %s' % (self._updated[i],
                                                 self[i])
        return response

    def rollback(self):
        '''
        Drop all not applied changes and rollback transaction.
        '''
        for i in self['ipaddr'].added:
            self['ipaddr'].remove(i, track=False)
        for i in self['ipaddr'].removed:
            self['ipaddr'].add(i, track=False)
        self['ipaddr'].cleanup()
        for i in tuple(self._updated.keys()):
            self[i] = self._updated[i]
            del self._updated[i]

    def commit(self):
        '''
        Commit transaction. In the case of exception all
        changes applied during commit will be reverted.
        '''
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
            for key in self._updated:
                if key in self._fields:
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
                for key in tuple(self._updated.keys()):
                    if key in self._fields:
                        request[key] = self._updated[key]
                        del self._updated[key]
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
        '''
        Shortcut: change interface state to 'up'.

        Requres commit.
        '''
        self['flags'] |= 1

    def down(self):
        '''
        Shortcut: change interface state to 'down'.

        Requires commit.
        '''
        self['flags'] &= ~(self['flags'] & 1)


class ipdb(dotkeys):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.

    No methods of the class should be called directly.
    '''

    def __init__(self, ipr=None, host='localsystem',
                 key=None, cert=None, ca=None):
        '''
        Parameters:
            * ipr -- iproute() reference

        If you do not provide iproute instance, ipdb will
        start it automatically. Please note, that there can
        be only one iproute instance per process. Actually,
        you can start two and more iproute instances, but
        only the first one will receive anything.
        '''
        self.ip = ipr or iproute(host=host, key=key, cert=cert, ca=ca)

        # caches
        self.ipaddr = {}
        self.routes = {}
        self.neighbors = {}

        # load information on startup
        links = self.ip.get_links()
        self.update_links(links)
        self.update_slaves(links)
        self.update_addr(self.ip.get_addr())

        # start monitoring thread
        self.ip.monitor()
        self.ip.mirror()
        self._mthread = threading.Thread(target=self.monitor)
        self._mthread.setDaemon(True)
        self._mthread.start()

    def update_links(self, links):
        '''
        Rebuild links index from list of RTM_NEWLINK messages.
        '''
        for dev in links:
            if dev['index'] not in self.ipaddr:
                self.ipaddr[dev['index']] = upset()
            i = self[dev['index']] = interface(dev, self.ip, self)
            self[i['ifname']] = i

    def update_slaves(self, links):
        '''
        Update slaves list -- only after update IPDB!
        '''
        for msg in links:
            master = msg.get_attr('IFLA_MASTER')
            if master:
                master = self[master[0]]
                index = msg['index']
                name = msg.get_attr('IFLA_IFNAME')[0]
                if msg['event'] == 'RTM_NEWLINK':
                    master._slaves[index] = self[msg['index']]
                    master._slaves[name] = self[msg['index']]
                elif msg['event'] == 'RTM_DELLINK':
                    if index in master._slaves:
                        del master._slaves[index]
                    if name in master._slaves:
                        del master._slaves[name]
                    if 'master' in self[msg['index']]:
                        del self[msg['index']]['master']

    def update_addr(self, addrs, action='add'):
        '''
        Update interface list of an interface.
        '''
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
        '''
        Main monitoring cycle. It gets messages from the
        default iproute queue and updates objects in the
        database.
        '''
        while True:
            try:
                messages = self.ip.get()
            except:
                continue
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
                            # FIXME catch exception
                            del self[old_name]
                            self[self[index]['ifname']] = self[index]
                    else:
                        self.update_links([msg])
                    self.update_slaves([msg])
                elif msg.get('event', None) == 'RTM_DELLINK':
                    self.update_slaves([msg])
                    if msg['change'] == 0xffffffff:
                        # FIXME catch exception
                        del self[self[msg['index']]['ifname']]
                        del self[msg['index']]
                elif msg.get('event', None) == 'RTM_NEWADDR':
                    self.update_addr([msg], 'add')
                elif msg.get('event', None) == 'RTM_DELADDR':
                    self.update_addr([msg], 'remove')
