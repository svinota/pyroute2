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
import re
import uuid
import threading
from socket import AF_INET
from socket import AF_INET6
from pyroute2.netlink.iproute import iproute
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

nla_fields = [ifinfmsg.nla2name(i[0]) for i in ifinfmsg.nla_map]
nla_fields.append('flags')
nla_fields.append('mask')
nla_fields.append('change')
nla_fields.append('state')

_var_name = re.compile('^[a-zA-Z_]+[a-zA-Z_0-9]*$')


def get_addr_nla(msg):
    '''
    Incosistency in Linux IP addressing scheme is that
    IPv4 uses IFA_LOCAL to store interface's ip address,
    and IPv6 uses for the same IFA_ADDRESS.

    IPv4 sets IFA_ADDRESS to == IFA_LOCAL or to a
    tunneling endpoint.
    '''
    nla = None
    if msg['family'] == AF_INET:
        nla = msg.get_attr('IFA_LOCAL')[0]
    elif msg['family'] == AF_INET6:
        nla = msg.get_attr('IFA_ADDRESS')[0]
    return nla


class ipset(set):

    def __init__(self, *argv, **kwarg):
        set.__init__(self, *argv, **kwarg)
        self.raw = {}
        self.links = []

    def add(self, key, raw=None):
        self.raw[key] = raw
        set.add(self, key)
        for link in self.links:
            link.add(key, raw)

    def remove(self, key, raw=None):
        for link in self.links:
            if key in link:
                link.remove(key)
        set.remove(self, key)

    def connect(self, link):
        assert isinstance(link, ipset)
        self.links.append(link)


class dotkeys(dict):

    def __dir__(self):
        return [i for i in self if type(i) == str and _var_name.match(i)]

    def __getattribute__(self, key, *argv):
        try:
            return dict.__getattribute__(self, key)
        except AttributeError as e:
            if key == '__deepcopy__':
                raise e
            return self[key]

    def __setattr__(self, key, value):
        if key in self:
            self[key] = value
        else:
            dict.__setattr__(self, key, value)

    def __delattr__(self, key):
        if key in self:
            del self[key]


class rwState(object):

    def __init__(self):
        self._rlock = threading.Lock()
        self._wlock = threading.Lock()
        self._lock = threading.Lock()
        self._readers = 0
        self._no_readers = threading.Event()
        self._no_readers.set()
        self._state = False

    def __enter__(self):
        self.reader_acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.reader_release()

    def reader_acquire(self):
        with self._wlock:
            with self._rlock:
                self._no_readers.clear()
                self._readers += 1

    def reader_release(self):
        with self._rlock:
            assert self._readers > 0
            self._readers -= 1
            if self._readers == 0:
                self._no_readers.set()

    def is_set(self):
        return self._state

    def acquire(self):
        self._lock.acquire()
        self._no_readers.wait()
        self._state = True

    def release(self):
        with self._wlock:
            self._no_readers.wait()
            self._state = False
            self._lock.release()


class IPDBError(Exception):
    pass


class IPDBTransactionRequired(IPDBError):
    pass


def update(f):
    def decorated(self, *argv, **kwarg):
        # obtain update lock
        with self._snapshot_lock:
            # fix the pass-through mode:
            with self._direct_state:
                kwarg['direct'] = self._direct_state.is_set()
                if not kwarg['direct']:
                    # 1. begin transaction for 'direct' type
                    if self._mode == 'direct':
                        self.begin()
                    # 2. begin transaction, if there is none
                    elif self._mode == 'implicit':
                        if not self._tids:
                            self.begin()
                    # 3. require open transaction for 'explicit' type
                    elif self._mode == 'explicit':
                        if not self._tids:
                            raise IPDBTransactionRequired()
                    # 4. transactions can not require transactions :)
                    elif self._mode == 'snapshot':
                        kwarg['direct'] = True
                    # do not support other modes
                    else:
                        raise IPDBError('transaction mode not supported')
                    # now that the transaction _is_ open
                f(self, *argv, **kwarg)
                if not kwarg['direct']:
                    # close the transaction for 'direct' type
                    if self._mode == 'direct':
                        self.commit()
    return decorated


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
    def __init__(self, dev=None, ipr=None, parent=None, mode='direct'):
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
        self.uid = uuid.uuid4()
        self.cleanup = ('header',
                        'linkinfo',
                        'af_spec',
                        'attrs',
                        'event',
                        'map',
                        'stats',
                        'stats64')
        self.last_error = None
        self._direct_state = rwState()
        self._parent = parent
        self._tids = []
        self._transactions = {}
        self._mode = mode
        self._slaves = dotkeys()
        self._snapshot_lock = threading.RLock()
        # local setup: direct state is required
        self._direct_state.acquire()
        self['ipaddr'] = ipset()
        self._direct_state.release()
        # 8<-----------------------------------
        if dev is not None:
            self.load(dev)

    def pick(self, detached=True):
        '''
        Get a snapshot of the interface state. Can be of two
        types:
            * detached=True -- (default) "true" snapshot
            * detached=False -- keep ip addr set updated from OS

        Please note, that "updated" doesn't mean "in sync".
        The reason behind this logic is that snapshots can be
        used as transactions.
        '''
        with self._snapshot_lock:
            res = interface(ipr=self.ip, mode='snapshot')
            for key in tuple(self.keys()):
                if key in nla_fields:
                    res[key] = self[key]
            res['ipaddr'] = ipset(self['ipaddr'])
            if self._parent is not None and not detached:
                self['ipaddr'].connect(res['ipaddr'])
            return res

    def __sub__(self, pif):
        '''
        '''
        res = interface(ipr=self.ip, mode='snapshot')
        # simple keys
        for key in self:
            if (key in nla_fields) and \
                    ((key not in pif) or (self[key] != pif[key])):
                res[key] = self[key]
        # ip addresses
        ipaddr = ipset(self['ipaddr'] - pif['ipaddr'])
        if ipaddr:
            res['ipaddr'] = ipaddr

        return res

    def __hash__(self):
        return self['index']

    def __enter__(self):
        self.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.commit()
        except Exception as e:
            self.last_error = e

    @property
    def if_master(self):
        '''
        [property] Link to the parent interface -- if it exists
        '''
        if 'master' in self:
            # bridge ports
            return self._parent.get(self['master'], None)
        elif 'link' in self:
            # vlan ports
            return self._parent.get(self['link'], None)

    @property
    def if_slaves(self):
        '''
        [property] Dictionary of slave interfaces
        '''
        return self._slaves

    def load(self, dev):
        '''
        Update the interface info from RTM_NEWLINK message.

        This call always bypasses open transactions, loading
        changes directly into the interface data.
        '''
        self._direct_state.acquire()
        self.update(dev)
        self._attrs = set()
        for (name, value) in dev['attrs']:
            norm = ifinfmsg.nla2name(name)
            self._attrs.add(norm)
            self[norm] = value
        # load interface kind
        linkinfo = dev.get_attr('IFLA_LINKINFO')
        if linkinfo:
            kind = linkinfo[0].get_attr('IFLA_INFO_KIND')
            if kind:
                self['kind'] = kind[0]
                if kind[0] == 'vlan':
                    data = linkinfo[0].get_attr('IFLA_INFO_DATA')[0]
                    self['vlan_id'] = data.get_attr('IFLA_VLAN_ID')[0]
        # the rest is possible only when interface
        # is used in IPDB, not standalone
        if self._parent is not None:
            # connect IP address set from IPDB
            self['ipaddr'] = self._parent.ipaddr[self['index']]
        # finally, cleanup all not needed
        for item in self.cleanup:
            if item in self:
                del self[item]
        self._direct_state.release()

    @update
    def __setitem__(self, key, value, direct):
        if not direct:
            transaction = self.last()
            transaction[key] = value
        else:
            dotkeys.__setitem__(self, key, value)

    @update
    def __delitem__(self, key, direct):
        if not direct:
            transaction = self.last()
            if key in transaction:
                del transaction[key]
        else:
            dotkeys.__delitem__(self, key)

    @update
    def add_ip(self, ip, mask, direct):
        if not direct:
            transaction = self.last()
            transaction.add_ip(ip, mask)
        else:
            self['ipaddr'].add((ip, mask))

    @update
    def del_ip(self, ip, mask, direct):
        if not direct:
            transaction = self.last()
            if (ip, mask) in transaction['ipaddr']:
                transaction.del_ip(ip, mask)
        else:
            self['ipaddr'].remove((ip, mask))

    def begin(self):
        '''
        Start new transaction
        '''
        # keep snapshot's ip addr set updated from the OS
        # it is required by the commit logic
        t = self.pick(detached=False)
        self._transactions[t.uid] = t
        self._tids.append(t.uid)
        return t.uid

    def last(self):
        '''
        Return last open transaction
        '''
        if not self._tids:
            raise IPDBTransactionRequired()
        return self._transactions[self._tids[-1]]

    def review(self):
        '''
        Review last open transaction
        '''
        if not self._tids:
            raise IPDBTransactionRequired()
        added = self.last() - self
        removed = self - self.last()
        added['-ipaddr'] = removed['ipaddr']
        added['+ipaddr'] = added['ipaddr']
        del added['ipaddr']
        return added

    def drop(self):
        '''
        Drop all not applied changes and rollback transaction.
        '''
        del self._transactions[self._tids.pop()]

    def commit(self, tid=None, transaction=None, rollback=False):
        '''
        Commit transaction. In the case of exception all
        changes applied during commit will be reverted.
        '''
        e = None
        snapshot = self.pick()
        if tid:
            transaction = self._transactions[tid]
        else:
            transaction = transaction or self.last()
        try:
            # commit IP address changes
            removed = self - transaction
            for i in removed['ipaddr']:
                self.ip.addr_del(self['index'], i[0], i[1])

            added = transaction - self
            for i in added['ipaddr']:
                self.ip.addr_add(self['index'], i[0], i[1])

            # commit interface changes
            request = {}
            for key in added:
                if key in nla_fields:
                    request[key] = added[key]

            # apply changes only if there is something to apply
            if request:
                self.ip.link('set', self['index'], **request)

        except Exception as e:
            # something went wrong: roll the transaction back
            if not rollback:
                # self.load(self.ip.get_links(self['index'])[0])
                self.commit(transaction=snapshot, rollback=True)
            else:
                # somethig went wrong during automatic rollback.
                # that's the worst case, but it is still possible,
                # since we have no locks on OS level.
                self.drop()
                raise e

        # if it is not a rollback turn
        if not rollback:
            # drop last transaction in any case
            self.drop()
            # re-load interface information
            # self.load(self.ip.get_links(self['index'])[0])

        # raise exception for failed transaction
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

    def __init__(self, ipr=None, host='localsystem', mode='implicit',
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
        self.mode = mode
        self._stop = False

        # resolvers
        self.by_name = dotkeys()
        self.by_index = dotkeys()

        # caches
        self.ipaddr = {}
        self.routes = {}
        self.neighbors = {}
        self.old_names = {}

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

    def __dir__(self):
        ret = dotkeys.__dir__(self)
        ret.append('by_name')
        ret.append('by_index')
        return ret

    def shutdown(self):
        self._stop = True
        self.ip.get_links()
        self.ip.shutdown_sockets()

    def update_links(self, links):
        '''
        Rebuild links index from list of RTM_NEWLINK messages.
        '''
        for dev in links:
            if dev['index'] not in self.ipaddr:
                self.ipaddr[dev['index']] = ipset()
            i = \
                self.by_index[dev['index']] = \
                self[dev['index']] = \
                interface(dev, self.ip, self, mode=self.mode)
            self[i['ifname']] = \
                self.by_name[i['ifname']] = i
            self.old_names[dev['index']] = i['ifname']

    def update_slaves(self, links):
        '''
        Update slaves list -- only after update IPDB!
        '''
        for msg in links:
            master = msg.get_attr('IFLA_MASTER') or \
                msg.get_attr('IFLA_LINK')
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
                    method(key=(nla, addr['prefixlen']), raw=addr)
                except:
                    pass

    def monitor(self):
        '''
        Main monitoring cycle. It gets messages from the
        default iproute queue and updates objects in the
        database.
        '''
        while not self._stop:
            try:
                messages = self.ip.get()
            except:
                continue
            for msg in messages:
                if msg.get('event', None) == 'RTM_NEWLINK':
                    index = msg['index']
                    if index in self:
                        # get old name
                        old = self.old_names[index]
                        # load interface from the message
                        self[index].load(msg)
                        # check for new name
                        if self[index]['ifname'] != old:
                            # FIXME catch exception
                            # FIXME isolate dict updates
                            if self[old].if_master:
                                del self[old].if_master.if_slaves[old]
                            del self[old]
                            del self.by_name[old]
                            if index in self.old_names:
                                del self.old_names[index]
                            self[self[index]['ifname']] = self[index]
                            self.by_name[self[index]['ifname']] = self[index]
                            self.old_names[index] = self[index]['ifname']
                    else:
                        self.update_links([msg])
                    self.update_slaves([msg])
                elif msg.get('event', None) == 'RTM_DELLINK':
                    self.update_slaves([msg])
                    if msg['change'] == 0xffffffff:
                        # FIXME catch exception
                        del self.by_name[self[msg['index']]['ifname']]
                        del self.by_index[msg['index']]
                        del self.old_names[msg['index']]
                        del self[self[msg['index']]['ifname']]
                        del self[msg['index']]
                elif msg.get('event', None) == 'RTM_NEWADDR':
                    self.update_addr([msg], 'add')
                elif msg.get('event', None) == 'RTM_DELADDR':
                    self.update_addr([msg], 'remove')
