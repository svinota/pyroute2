'''
Experimental IP database module. Please, do not use it
unless you understand what are you doing.

Quick start:
    from pyroute2 import IPDB
    ip = IPDB()
    ip.interfaces['eth0']['address'] = '00:11:22:33:44:55'
    ip.interfaces['eth0']['ifname'] = 'bala'
    ip.interfaces['eth0']['txqlen'] = 2000
    ip.interfaces['eth0'].commit()
    ip.routes.add({'dst': 'default', 'gateway': '10.0.0.1'}).commit()
'''
import os
import uuid
import threading
try:
    from Queue import Empty
except ImportError:
    from queue import Empty

from socket import AF_UNSPEC
from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import Dotkeys
from pyroute2.netlink import NetlinkError
from pyroute2.netlink.ipdb import compat
from pyroute2.netlink.iproute import IPRoute
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.tcmsg import tcmsg

tc_fields = [tcmsg.nla2name(i[0]) for i in tcmsg.nla_map]


# How long should we wait on EACH commit() checkpoint: for ipaddr,
# ports etc. That's not total commit() timeout.
_SYNC_TIMEOUT = 3

_FAIL_COMMIT = 0b00000001
_FAIL_ROLLBACK = 0b00000010
_FAIL_MASK = 0b11111111


def clear_fail_bit(bit):
    global _FAIL_MASK
    _FAIL_MASK &= ~(_FAIL_MASK & bit)


def set_fail_bit(bit):
    global _FAIL_MASK
    _FAIL_MASK |= bit


def get_interface_type(name):
    '''
    Utility function to get interface type
    '''
    # we can not even rely on ioctl(), since RHEL does not support
    # extended (private) interface flags :(((
    try:
        ifattrs = os.listdir('/sys/class/net/%s/' % (name))
    except OSError as e:
        if e.errno == 2:
            return False
        else:
            raise

    if 'bonding' in ifattrs:
        return 'bond'
    elif 'bridge' in ifattrs:
        return 'bridge'
    else:
        return None


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
        nla = msg.get_attr('IFA_LOCAL')
    elif msg['family'] == AF_INET6:
        nla = msg.get_attr('IFA_ADDRESS')
    return nla


class LinkedSet(set):

    def __init__(self, *argv, **kwarg):
        set.__init__(self, *argv, **kwarg)
        self.lock = threading.RLock()
        self.target = threading.Event()
        self._ct = None
        self.raw = {}
        self.links = []

    def set_target(self, value):
        with self.lock:
            if value is None:
                self._ct = None
                self.target.clear()
            else:
                self._ct = set(value)
                self.target.clear()

    def check_target(self):
        with self.lock:
            if self._ct is not None:
                if self == self._ct:
                    self._ct = None
                    self.target.set()

    def add(self, key, raw=None):
        with self.lock:
            if key not in self:
                self.raw[key] = raw
                set.add(self, key)
                for link in self.links:
                    link.add(key, raw)
            self.check_target()

    def remove(self, key, raw=None):
        with self.lock:
            set.remove(self, key)
            for link in self.links:
                if key in link:
                    link.remove(key)
            self.check_target()

    def connect(self, link):
        assert isinstance(link, LinkedSet)
        self.links.append(link)

    def __repr__(self):
        return repr(list(self))


class State(object):

    def __init__(self, lock=None):
        self.lock = lock or threading.Lock()
        self.flag = 0

    def acquire(self):
        self.lock.acquire()
        self.flag += 1

    def release(self):
        assert self.flag > 0
        self.flag -= 1
        self.lock.release()

    def is_set(self):
        return self.flag

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


def update(f):
    def decorated(self, *argv, **kwarg):
        # obtain update lock
        tid = None
        direct = True
        with self._write_lock:
            dcall = kwarg.pop('direct', False)
            if dcall:
                self._direct_state.acquire()

            direct = self._direct_state.is_set()
            if not direct:
                # 1. begin transaction for 'direct' type
                if self._mode == 'direct':
                    tid = self.begin()
                # 2. begin transaction, if there is none
                elif self._mode == 'implicit':
                    if not self._tids:
                        self.begin()
                # 3. require open transaction for 'explicit' type
                elif self._mode == 'explicit':
                    if not self._tids:
                        raise TypeError('start a transaction first')
                # 4. transactions can not require transactions :)
                elif self._mode == 'snapshot':
                    direct = True
                # do not support other modes
                else:
                    raise TypeError('transaction mode not supported')
                # now that the transaction _is_ open
            f(self, direct, *argv, **kwarg)

            if dcall:
                self._direct_state.release()

        if tid:
            # close the transaction for 'direct' type
            self.commit(tid)
    return decorated


class IPRequest(dict):

    def __init__(self, obj=None):
        dict.__init__(self)
        if obj is not None:
            self.update(obj)

    def update(self, obj):
        for key in obj:
            if obj[key] is not None:
                self[key] = obj[key]


class IPRouteRequest(IPRequest):

    def __setitem__(self, key, value):
        if (key == 'dst') and (value != 'default'):
            value = value.split('/')
            if len(value) == 1:
                dst = value[0]
                mask = 0
            elif len(value) == 2:
                dst = value[0]
                mask = int(value[1])
            else:
                raise ValueError('wrong destination')
            dict.__setitem__(self, 'dst', dst)
            dict.__setitem__(self, 'dst_len', mask)
        elif key != 'dst':
            dict.__setitem__(self, key, value)


class IPLinkRequest(IPRequest):

    def __setitem__(self, key, value):
        if key == 'kind':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_KIND', value]
            # FIXME: we need to replace, not add
            self['IFLA_LINKINFO']['attrs'].append(nla)
        elif key == 'vlan_id':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_DATA', {'attrs': [['IFLA_VLAN_ID', value]]}]
            # FIXME: we need to replace, not add
            self['IFLA_LINKINFO']['attrs'].append(nla)
        elif key == 'bond_mode':
            if 'IFLA_LINKINFO' not in self:
                self['IFLA_LINKINFO'] = {'attrs': []}
            nla = ['IFLA_INFO_DATA', {'attrs': [['IFLA_BOND_MODE', value]]}]
            self['IFLA_LINKINFO']['attrs'].append(nla)
        dict.__setitem__(self, key, value)


class Transactional(Dotkeys):
    '''
    An utility class that implements common transactional logic.
    '''
    def __init__(self, ipdb, mode=None):
        self.nl = ipdb.nl
        self.uid = uuid.uuid4()
        self.ipdb = ipdb
        self.last_error = None
        self._callbacks = []
        self._fields = []
        self._tids = []
        self._transactions = {}
        self._mode = mode or ipdb.mode
        self._write_lock = threading.RLock()
        self._direct_state = State(self._write_lock)
        self._linked_sets = set()

    def register_callback(self, callback):
        self._callbacks.append(callback)

    def unregister_callback(self, callback):
        for cb in tuple(self._callbacks):
            if callback == cb:
                self._callbacks.pop(self._callbacks.index(cb))

    def pick(self, detached=True):
        '''
        Get a snapshot of the object. Can be of two
        types:
            * detached=True -- (default) "true" snapshot
            * detached=False -- keep ip addr set updated from OS

        Please note, that "updated" doesn't mean "in sync".
        The reason behind this logic is that snapshots can be
        used as transactions.
        '''
        with self._write_lock:
            res = self.__class__(ipdb=self.ipdb, mode='snapshot')
            for key in tuple(self.keys()):
                if key in self._fields:
                    res[key] = self[key]
            for key in self._linked_sets:
                res[key] = LinkedSet(self[key])
                if not detached:
                    self[key].connect(res[key])
            return res

    def __enter__(self):
        # FIXME: use a bitmask?
        if self._mode not in ('implicit', 'explicit'):
            raise TypeError('context managers require a transactional mode')
        if not self._tids:
            self.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # apply transaction only if there was no error
        if exc_type is None:
            try:
                self.commit()
            except Exception as e:
                self.last_error = e
                raise

    def __repr__(self):
        res = {}
        for i in self:
            if self[i] is not None:
                res[i] = self[i]
        return res.__repr__()

    def __sub__(self, vs):
        '''
        '''
        res = self.__class__(ipdb=self.ipdb, mode='snapshot')
        with self._direct_state:
            # simple keys
            for key in self:
                if (key in self._fields) and \
                        ((key not in vs) or (self[key] != vs[key])):
                    res[key] = self[key]
        for key in self._linked_sets:
            diff = LinkedSet(self[key] - vs[key])
            if diff:
                res[key] = diff
        return res

    def commit(self, *args, **kwarg):
        pass

    def begin(self):
        '''
        Start new transaction
        '''
        # keep snapshot's ip addr set updated from the OS
        # it is required by the commit logic
        with self.ipdb.exclusive:
            if self.ipdb._stop:
                raise RuntimeError("Can't start transaction on released IPDB")
            t = self.pick(detached=False)
            self._transactions[t.uid] = t
            self._tids.append(t.uid)
            return t.uid

    def last(self):
        '''
        Return last open transaction
        '''
        if not self._tids:
            raise TypeError('start a transaction first')

        return self._transactions[self._tids[-1]]

    def review(self):
        '''
        Review last open transaction
        '''
        if not self._tids:
            raise TypeError('start a transaction first')

        added = self.last() - self
        removed = self - self.last()
        for key in self._linked_sets:
            added['-%s' % (key)] = removed[key]
            added['+%s' % (key)] = added[key]
            del added[key]
        return added

    def drop(self):
        '''
        Drop all not applied changes and rollback transaction.
        '''
        del self._transactions[self._tids.pop()]

    @update
    def __setitem__(self, direct, key, value):
        if not direct:
            transaction = self.last()
            transaction[key] = value
        else:
            Dotkeys.__setitem__(self, key, value)

    @update
    def __delitem__(self, direct, key):
        if not direct:
            transaction = self.last()
            if key in transaction:
                del transaction[key]
        else:
            Dotkeys.__delitem__(self, key)

    def set_item(self, key, value):
        with self._direct_state:
            self[key] = value

    def del_item(self, key):
        with self._direct_state:
            del self[key]


class TrafficControl(Transactional):
    '''
    '''
    def __init__(self, ipdb, mode=None):
        Transactional.__init__(self, ipdb, mode)
        self._fields = tc_fields

    def load(self, msg):
        with self._direct_state:
            self.update(msg)
            self['kind'] = msg.get_attr('TCA_KIND')

    def set_filter(self, kind, **kwarg):
        pass

    def set_control(self, kind, **kwarg):
        pass

    def remove(self):
        pass


class Interface(Transactional):
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
    def __init__(self, ipdb, mode=None):
        '''
        One can use interface objects standalone as
        well as in connection with ipdb object. Standalone
        usage, though, is discouraged.

        Parameters:
            * nl   -- IPRoute() reference
            * ipdb -- ipdb() reference
            * mode -- transaction mode
        '''
        Transactional.__init__(self, ipdb, mode)
        self.cleanup = ('header',
                        'linkinfo',
                        'af_spec',
                        'attrs',
                        'event',
                        'map',
                        'stats',
                        'stats64')
        self.ingress = None
        self.egress = None
        self._exists = False
        self._fields = [ifinfmsg.nla2name(i[0]) for i in ifinfmsg.nla_map]
        self._fields.append('flags')
        self._fields.append('mask')
        self._fields.append('change')
        self._fields.append('state')
        self._fields.append('removal')
        self._fields.append('flicker')
        self._load_event = threading.Event()
        self._linked_sets.add('ipaddr')
        self._linked_sets.add('ports')
        # 8<-----------------------------------
        # local setup: direct state is required
        with self._direct_state:
            self['ipaddr'] = LinkedSet()
            self['ports'] = LinkedSet()
            for i in self._fields:
                self[i] = None
            for i in ('state', 'change', 'mask'):
                del self[i]
        # 8<-----------------------------------

    def __hash__(self):
        return self['index']

    @property
    def if_master(self):
        '''
        [property] Link to the parent interface -- if it exists
        '''
        ret = [self[i] for i in ('link', 'master')
               if (i in self) and isinstance(self[i], int)] or [None]
        return ret[0]

    def load(self, dev):
        '''
        Update the interface info from RTM_NEWLINK message.

        This call always bypasses open transactions, loading
        changes directly into the interface data.
        '''
        with self._direct_state:
            self._exists = True
            self.update(dev)
            for (name, value) in dev['attrs']:
                norm = ifinfmsg.nla2name(name)
                self[norm] = value
            # load interface kind
            linkinfo = dev.get_attr('IFLA_LINKINFO')
            if linkinfo is not None:
                kind = linkinfo.get_attr('IFLA_INFO_KIND')
                if kind is not None:
                    self['kind'] = kind
                    if kind == 'vlan':
                        data = linkinfo.get_attr('IFLA_INFO_DATA')
                        self['vlan_id'] = data.get_attr('IFLA_VLAN_ID')
            # the rest is possible only when interface
            # is used in IPDB, not standalone
            if self.ipdb is not None:
                # connect IP address set from IPDB
                self['ipaddr'] = self.ipdb.ipaddr[self['index']]
            # load the interface type
            if 'kind' not in self:
                kind = get_interface_type(self['ifname'])
                if kind is not False:
                    self['kind'] = kind
            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]

            self.sync()

    def sync(self):
        self._load_event.set()

    @update
    def add_ip(self, direct, ip, mask=None):
        # split mask
        if mask is None:
            ip, mask = ip.split('/')
            mask = int(mask, 0)
        # FIXME: make it more generic
        # skip IPv6 link-local addresses
        if ip[:4] == 'fe80' and mask == 64:
            return
        if not direct:
            transaction = self.last()
            transaction.add_ip(ip, mask)
        else:
            self['ipaddr'].add((ip, mask))

    @update
    def del_ip(self, direct, ip, mask=None):
        if mask is None:
            ip, mask = ip.split('/')
            mask = int(mask, 0)
        if not direct:
            transaction = self.last()
            if (ip, mask) in transaction['ipaddr']:
                transaction.del_ip(ip, mask)
        else:
            self['ipaddr'].remove((ip, mask))

    @update
    def add_port(self, direct, port):
        if isinstance(port, Interface):
            port = port['index']
        if not direct:
            transaction = self.last()
            transaction.add_port(port)
        else:
            compat.fix_add_master(self.ipdb.interfaces[port], self)
            self['ports'].add(port)

    @update
    def del_port(self, direct, port):
        if isinstance(port, Interface):
            port = port['index']
        if not direct:
            transaction = self.last()
            if port in transaction['ports']:
                transaction.del_port(port)
        else:
            compat.fix_del_master(self.ipdb.interfaces[port])
            # FIXME: do something with it, please
            self['ports'].remove(port)

    def reload(self):
        '''
        Reload interface information
        '''
        self._load_event.clear()
        for i in range(3):
            try:
                self.nl.get_links(self['index'])
                break
            except NetlinkError as e:
                if e.code != 22:  # Invalid argument, try again
                    raise
            except Empty:
                raise IOError('lost netlink connection')
        self._load_event.wait()

    def commit(self, tid=None, transaction=None, rollback=False):
        '''
        Commit transaction. In the case of exception all
        changes applied during commit will be reverted.
        '''
        error = None
        added = None
        removed = None
        if tid:
            transaction = self._transactions[tid]
        else:
            transaction = transaction or self.last()

        # if the interface does not exist, create it first ;)
        if not self._exists:
            request = IPLinkRequest(self)
            self.ipdb._links_event.clear()
            try:
                compat.fix_create_link(self.nl, request)
            except Exception:
                # on failure, invalidate the interface and detach it
                # from the parent
                # 1. drop the IPRoute() link
                self.nl = None
                # 2. clean up ipdb
                self.ipdb.detach(self['index'])
                self.ipdb.detach(self['ifname'])
                # 3. invalidate the interface
                with self._direct_state:
                    for i in tuple(self.keys()):
                        del self[i]
                # 4. the rest
                self._mode = 'invalid'
                # raise the exception
                raise

            # all is OK till now, so continue
            # we do not know what to load, so load everything
            self.nl.get_links()
            self.ipdb._links_event.wait()

        # now we have our index and IP set and all other stuff
        snapshot = self.pick()

        try:
            removed = snapshot - transaction
            added = transaction - snapshot

            # 8<---------------------------------------------
            # IP address changes
            self['ipaddr'].set_target(transaction['ipaddr'])

            for i in removed['ipaddr']:
                # When you remove a primary IP addr, all subnetwork
                # can be removed. In this case you will fail, but
                # it is OK, no need to roll back
                try:
                    self.nl.addr('delete', self['index'], i[0], i[1])
                except NetlinkError as x:
                    # bypass only errno 99, 'Cannot assign address'
                    if x.code != 99:
                        raise

            for i in added['ipaddr']:
                self.nl.addr('add', self['index'], i[0], i[1])

            if removed['ipaddr'] or added['ipaddr']:
                self['ipaddr'].target.wait(_SYNC_TIMEOUT)
                assert self['ipaddr'].target.is_set()

            # 8<---------------------------------------------
            # Interface slaves
            self['ports'].set_target(transaction['ports'])

            for i in removed['ports']:
                # detach the port
                compat.fix_del_port(self.nl, self, self.ipdb.interfaces[i])

            for i in added['ports']:
                # enslave the port
                compat.fix_add_port(self.nl, self, self.ipdb.interfaces[i])

            if removed['ports'] or added['ports']:
                self.nl.get_links(*(removed['ports'] | added['ports']))
                self['ports'].target.wait(_SYNC_TIMEOUT)
                assert self['ports'].target.is_set()

            # 8<---------------------------------------------
            # Interface changes
            request = IPLinkRequest()
            for key in added:
                if key in self._fields:
                    request[key] = added[key]

            # apply changes only if there is something to apply
            if any([request[item] is not None for item in request]):
                self.nl.link('set', index=self['index'], **request)

            # 8<---------------------------------------------
            # Interface removal
            if added.get('removal') or added.get('flicker'):
                self._load_event.clear()
                if added.get('flicker'):
                    self.ipdb.flicker.add(self['index'])
                compat.fix_del_link(self.nl, self)
                self._load_event.wait(_SYNC_TIMEOUT)
                assert self._load_event.is_set()
                if added.get('flicker'):
                    self.ipdb.flicker.remove(self['index'])
                    self._exists = False
                    self.set_item('flicker', True)
                if added.get('removal'):
                    self._mode = 'invalid'
                self.drop()
                return
            # 8<---------------------------------------------

            if rollback:
                assert _FAIL_ROLLBACK & _FAIL_MASK
            else:

                # 8<-----------------------------------------
                # Iterate callback chain
                for cb in self._callbacks:
                    # An exception will rollback the transaction
                    cb(snapshot, transaction)
                # 8<-----------------------------------------

                assert _FAIL_COMMIT & _FAIL_MASK

        except Exception as e:
            # something went wrong: roll the transaction back
            if not rollback:
                self.reload()
                # 8<-----------------------------------------
                # That's a hack, but we have to use it, since
                # OS response can be not so fast
                # * inject added IPs directly into self
                # * wipe removed IPs from the interface data
                #
                # This info will be used to properly roll back
                # changes.
                #
                # Still, there is a possibility that the
                # rollback will run even before IP addrs will
                # be assigned. But we can not cope with that.
                with self._direct_state:
                    if removed:
                        for i in removed['ipaddr']:
                            try:
                                self['ipaddr'].remove(i)
                            except KeyError:
                                pass
                    if added:
                        for i in added['ipaddr']:
                            self['ipaddr'].add(i)
                # 8<-----------------------------------------
                ret = self.commit(transaction=snapshot, rollback=True)
                # if some error was returned by the internal
                # closure, substitute the initial one
                if ret is not None:
                    error = ret
                else:
                    error = e
            elif isinstance(e, NetlinkError) and getattr(e, 'code', 0) == 1:
                # It is <Operation not permitted>, catched in
                # rollback. So return it -- see ~5 lines above
                return e
            else:
                # somethig went wrong during automatic rollback.
                # that's the worst case, but it is still possible,
                # since we have no locks on OS level.
                self.drop()
                self['ipaddr'].set_target(None)
                self['ports'].set_target(None)
                # reload all the database -- it can take a long time,
                # but it is required since we have no idea, what is
                # the result of the failure
                #
                # ACHTUNG: database reload is asynchronous, so after
                # getting RuntimeError() from commit(), take a seat
                # and rest for a while. It is an extremal case, it
                # should not became at all, and there is no sync.
                self.nl.get_links()
                self.nl.get_addr()
                x = RuntimeError()
                x.cause = e
                raise x

        # if it is not a rollback turn
        if not rollback:
            # drop last transaction in any case
            self.drop()
            # re-load interface information
            self.reload()

        # raise exception for failed transaction
        if error is not None:
            error.transaction = transaction
            raise error

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

    def remove(self):
        self['removal'] = True

    def flicker(self):
        self['flicker'] = True


class Route(Transactional):

    def __init__(self, ipdb, mode=None):
        Transactional.__init__(self, ipdb, mode)
        self._exists = False
        self._load_event = threading.Event()
        self._fields = [rtmsg.nla2name(i[0]) for i in rtmsg.nla_map]
        self._fields.append('flags')
        self._fields.append('src_len')
        self._fields.append('dst_len')
        self._fields.append('table')
        self._fields.append('removal')
        self.cleanup = ('attrs',
                        'header',
                        'event')

    def load(self, msg):
        with self._direct_state:
            self._exists = True
            self['flicker'] = None
            self.update(msg)
            # merge key
            for (name, value) in msg['attrs']:
                norm = rtmsg.nla2name(name)
                self[norm] = value
            if msg.get_attr('RTA_DST', None) is not None:
                dst = '%s/%s' % (msg.get_attr('RTA_DST'),
                                 msg['dst_len'])
            else:
                dst = 'default'
            self['dst'] = dst
            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]

            self.sync()

    def sync(self):
        self._load_event.set()

    def reload(self):
        # do NOT call get_routes() here, it can cause race condition
        self._load_event.wait()

    def commit(self, tid=None, transaction=None, rollback=False):
        self._load_event.clear()
        error = None

        if tid:
            transaction = self._transactions[tid]
        else:
            transaction = transaction or self.last()

        # create a new route
        if not self._exists:
            try:
                self.nl.route('add', **IPRouteRequest(self))
            except Exception:
                self.nl = None
                self.ipdb.routes.remove(self)
                raise

        # work on existing route
        snapshot = self.pick()
        try:
            # route set
            request = IPRouteRequest(transaction - snapshot)
            if any([request[x] is not None for x in request]):
                self.nl.route('set', **IPRouteRequest(transaction))

            if transaction.get('removal'):
                self.nl.route('delete', **IPRouteRequest(snapshot))

        except Exception as e:
            if not rollback:
                ret = self.commit(transaction=snapshot, rollback=True)
                if ret is not None:
                    error = ret
                else:
                    error = e
            else:
                self.drop()
                x = RuntimeError()
                x.cause = e
                raise x

        if not rollback:
            self.drop()
            self.reload()

        if error is not None:
            error.transaction = transaction
            raise error

    def remove(self):
        self['removal'] = True


class RoutingTables(dict):

    def __init__(self, ipdb):
        dict.__init__(self)
        self.ipdb = ipdb
        self.tables = dict()

    def add(self, spec):
        '''
        Create a route from a dictionary
        '''
        table = spec.get('table', 254)
        assert 'dst' in spec
        route = Route(self.ipdb)
        route.update(spec)
        if table not in self.tables:
            self.tables[table] = dict()
        self.tables[table][route['dst']] = route
        route.begin()
        return route

    def load(self, msg):
        '''
        Loads an existing route from a rtmsg
        '''
        table = msg.get('table', 254)
        if table not in self.tables:
            self.tables[table] = dict()

        dst = msg.get_attr('RTA_DST', None)
        if dst is None:
            key = 'default'
        else:
            key = '%s/%s' % (dst, msg.get('dst_len', 0))

        if key in self.tables[table]:
            ret = self.tables[table][key]
            ret.load(msg)
        else:
            ret = Route(ipdb=self.ipdb)
            ret.load(msg)
            self.tables[table][key] = ret
        return ret

    def remove(self, route, table=None):
        if isinstance(route, Route):
            table = route.get('table', 254)
            route = route.get('dst', 'default')
        else:
            table = table or 254
        del self.tables[table][route]

    def get(self, dst, table=None):
        table = table or 254
        return self.tables[table][dst]

    def keys(self, table=254, family=AF_UNSPEC):
        return [x['dst'] for x in self.tables[table].values()
                if (x['family'] == family) or (family == AF_UNSPEC)]

    def has_key(self, key, table=254):
        return key in self.tables[table]

    def __contains__(self, key):
        return key in self.tables[254]

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        assert key == value['dst']
        return self.add(value)

    def __delitem__(self, key):
        return self.remove(key)


class IPDB(object):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.
    '''

    def __init__(self, nl=None, host=None, mode='implicit',
                 key=None, cert=None, ca=None, iclass=Interface,
                 fork=False):
        '''
        Parameters:
            * nl -- IPRoute() reference

        If you do not provide iproute instance, ipdb will
        start it automatically. Please note, that there can
        be only one iproute instance per process. Actually,
        you can start two and more iproute instances, but
        only the first one will receive anything.
        '''
        self.nl = nl or IPRoute(host=host,
                                key=key,
                                cert=cert,
                                ca=ca,
                                fork=fork)
        self.mode = mode
        self.iclass = iclass
        self._stop = False
        # see also 'register_callback'
        self._post_callbacks = []
        self._pre_callbacks = []
        self._cb_threads = set()

        # resolvers
        self.interfaces = Dotkeys()
        self.routes = RoutingTables(ipdb=self)
        self.by_name = Dotkeys()
        self.by_index = Dotkeys()

        # caches
        self.flicker = set()
        self.ipaddr = {}
        self.neighbors = {}

        # update events
        self._links_event = threading.Event()
        self.exclusive = threading.RLock()

        # load information on startup
        links = self.nl.get_links()
        for link in links:
            self.device_put(link, skip_slaves=True)
        for link in links:
            self.update_slaves(link)
        self.update_addr(self.nl.get_addr())
        routes = self.nl.get_routes()
        self.update_routes(routes)

        # start monitoring thread
        self.nl.monitor()
        self.nl.mirror()
        self._mthread = threading.Thread(target=self.serve_forever)
        self._mthread.setDaemon(True)
        self._mthread.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def register_callback(self, callback, mode='post'):
        '''
        IPDB callbacks are routines executed on a RT netlink
        message arrival. There are two types of callbacks:
        "post" and "pre" callbacks.

        ...

        "Post" callbacks are executed after the message is
        processed by IPDB and all corresponding objects are
        created or deleted. Using ipdb reference in "post"
        callbacks you will access the most up-to-date state
        of the IP database.

        "Post" callbacks are executed asynchronously in
        separate threads. These threads can work as long
        as you want them to. Callback threads are joined
        occasionally, so for a short time there can exist
        stopped threads.

        ...

        "Pre" callbacks are synchronous routines, executed
        before the message gets processed by IPDB. It gives
        you the way to patch arriving messages, but also
        places a restriction: until the callback exits, the
        main event IPDB loop is blocked.

        Normally, only "post" callbacks are required. But in
        some specific cases "pre" also can be useful.

        ...

        The routine, `register_callback()`, takes two arguments:
        1. callback function
        2. mode (optional, default="post")

        The callback should be a routine, that accepts three
        arguments::

            cb(ipdb, msg, action)

        1. ipdb is a reference to IPDB instance, that invokes
           the callback.
        2. msg is a message arrived
        3. action is just a msg['event'] field

        E.g., to work on a new interface, you should catch
        action == 'RTM_NEWLINK' and with the interface index
        (arrived in msg['index']) get it from IPDB::

            index = msg['index']
            interface = ipdb.interfaces[index]
        '''
        if mode == 'post':
            self._post_callbacks.append(callback)
        elif mode == 'pre':
            self._pre_callbacks.append(callback)

    def unregister_callback(self, callback, mode='post'):
        if mode == 'post':
            cbchain = self._post_callbacks
        elif mode == 'pre':
            cbchain = self._pre_callbacks
        else:
            raise KeyError('Unknown callback mode')
        for cb in tuple(cbchain):
            if callback == cb:
                cbchain.pop(cbchain.index(cb))

    def release(self):
        '''
        Shutdown monitoring thread and release iproute.
        '''
        with self.exclusive:
            self._stop = True
            self.nl.get_links()
            self.nl.release()
            self._mthread.join()

    def create(self, kind, ifname, **kwarg):
        '''
        Create an interface. Arguments 'kind' and 'ifname' are
        required.

        * kind -- interface type, can be of:
          * bridge
          * bond
          * vlan
          * tun
          * dummy
        * ifname -- interface name

        Different interface kinds can require different
        arguments for creation.

        FIXME: this should be documented.
        '''
        # check for existing interface
        if ((ifname in self.interfaces) and
                (self.interfaces[ifname]['flicker'])):
            device = self.interfaces[ifname]
        else:
            device = \
                self.by_name[ifname] = \
                self.interfaces[ifname] = \
                self.iclass(ipdb=self, mode='snapshot')
            device['kind'] = kind
            device['index'] = kwarg.get('index', 0)
            device['ifname'] = ifname
            device.update(kwarg)
            device._mode = self.mode
        device.begin()
        return device

    def device_del(self, msg):
        # check for flicker devices
        if (msg.get('index', None) in self.flicker):
            return
        try:
            self.update_slaves(msg)
            if msg['change'] == 0xffffffff:
                # FIXME catch exception
                ifname = self.interfaces[msg['index']]['ifname']
                self.interfaces[msg['index']].sync()
                del self.by_name[ifname]
                del self.by_index[msg['index']]
                del self.interfaces[ifname]
                del self.interfaces[msg['index']]
                del self.ipaddr[msg['index']]
        except KeyError:
            pass

    def device_put(self, msg, skip_slaves=False):
        # check, if a record exists
        index = msg.get('index', None)
        ifname = msg.get_attr('IFLA_IFNAME', None)
        # scenario #1: no matches for both: new interface
        # scenario #2: ifname exists, index doesn't: index changed
        # scenario #3: index exists, ifname doesn't: name changed
        # scenario #4: both exist: assume simple update and
        # an optional name change
        if ((index not in self.interfaces) and
                (ifname not in self.interfaces)):
            # scenario #1, new interface
            if compat.fix_check_link(self.nl, index):
                return
            device = \
                self.by_index[index] = \
                self.interfaces[index] = \
                self.interfaces[ifname] = \
                self.by_name[ifname] = self.iclass(ipdb=self)
        elif ((index not in self.interfaces) and
                (ifname in self.interfaces)):
            # scenario #2, index change
            old_index = self.interfaces[ifname]['index']
            device = \
                self.interfaces[index] = \
                self.by_index[index] = self.interfaces[ifname]
            if old_index in self.ipaddr:
                self.ipaddr[index] = self.ipaddr[old_index]
                del self.interfaces[old_index]
                del self.by_index[old_index]
                del self.ipaddr[old_index]
        else:
            # scenario #3, interface rename
            # scenario #4, assume rename
            old_name = self.interfaces[index]['ifname']
            if old_name != ifname:
                # unlink old name
                del self.interfaces[old_name]
                del self.by_name[old_name]
            device = \
                self.interfaces[ifname] = \
                self.by_name[ifname] = self.interfaces[index]

        if index not in self.ipaddr:
            # for interfaces, created by IPDB
            self.ipaddr[index] = LinkedSet()

        device.load(msg)
        if not skip_slaves:
            self.update_slaves(msg)

    def detach(self, item):
        if item in self.interfaces:
            del self.interfaces[item]

    def wait_interface(self, action='RTM_NEWLINK', **kwarg):
        event = threading.Event()

        def cb(self, msg, _action):
            if _action != action:
                return
            port = self.interfaces[msg['index']]
            for key in kwarg:
                if port.get(key, None) != kwarg[key]:
                    return
            event.set()

        # register callback prior to other things
        self.register_callback(cb)
        # inspect existing interfaces, as if they were created
        for index in self.by_index:
            cb(self, self.by_index[index], 'RTM_NEWLINK')
        # ok, wait the event
        event.wait()
        # unregister callback
        self.unregister_callback(cb)

    def update_routes(self, routes):
        for msg in routes:
            self.routes.load(msg)

    def _lookup_master(self, msg):
        index = msg['index']
        master = msg.get_attr('IFLA_MASTER') or \
            msg.get_attr('IFLA_LINK')
        if (master is None):
            master = compat.fix_lookup_master(self.interfaces[index])
        return self.interfaces.get(master, None)

    def update_slaves(self, msg):
        '''
        Update slaves list -- only after update IPDB!
        '''
        master = self._lookup_master(msg)
        index = msg['index']
        # there IS a master for the interface
        if master is not None:
            if msg['event'] == 'RTM_NEWLINK':
                # TODO tags: ipdb
                # The code serves one particular case, when
                # an enslaved interface is set to belong to
                # another master. In this case there will be
                # no 'RTM_DELLINK', only 'RTM_NEWLINK', and
                # we can end up in a broken state, when two
                # masters refers to the same slave
                for device in self.by_index:
                    if index in self.interfaces[device]['ports']:
                        self.interfaces[device].del_port(index,
                                                         direct=True)
                master.add_port(index, direct=True)
            elif msg['event'] == 'RTM_DELLINK':
                if index in master['ports']:
                    master.del_port(index, direct=True)
        # there is NO masters for the interface, clean them if any
        else:
            device = self.interfaces[msg['index']]

            # clean device from ports
            for master in self.by_index:
                if index in self.interfaces[master]['ports']:
                    self.interfaces[master].del_port(index,
                                                     direct=True)
            master = device.if_master
            if master is not None:
                if 'master' in device:
                    device.del_item('master')
                if 'link' in device:
                    device.del_item('link')
                if (master in self.interfaces) and \
                        (msg['index'] in self.interfaces[master].ports):
                    self.interfaces[master].del_port(msg['index'],
                                                     direct=True)

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

    def serve_forever(self):
        '''
        Main monitoring cycle. It gets messages from the
        default iproute queue and updates objects in the
        database.
        '''
        while not self._stop:
            try:
                messages = self.nl.get()
            except:
                continue
            for msg in messages:
                # run pre-callbacks
                # NOTE: pre-callbacks are synchronous
                for cb in self._pre_callbacks:
                    try:
                        cb(self, msg, msg['event'])
                    except:
                        pass

                if msg.get('event', None) == 'RTM_NEWLINK':
                    self.device_put(msg)
                    self._links_event.set()
                elif msg.get('event', None) == 'RTM_DELLINK':
                    self.device_del(msg)
                elif msg.get('event', None) == 'RTM_NEWADDR':
                    self.update_addr([msg], 'add')
                elif msg.get('event', None) == 'RTM_DELADDR':
                    self.update_addr([msg], 'remove')
                elif msg.get('event', None) == 'RTM_NEWROUTE':
                    self.update_routes([msg])
                elif msg.get('event', None) == 'RTM_DELROUTE':
                    table = msg.get('table', 254)
                    dst = msg.get_attr('RTA_DST', False)
                    if not dst:
                        key = 'default'
                    else:
                        key = '%s/%s' % (dst, msg.get('dst_len', 0))
                    try:
                        route = self.routes.tables[table][key]
                        del self.routes.tables[table][key]
                        route.sync()
                    except KeyError:
                        pass

                # run post-callbacks
                # NOTE: post-callbacks are asynchronous
                for cb in self._post_callbacks:
                    t = threading.Thread(name="callback %s" % (id(cb)),
                                         target=cb,
                                         args=(self, msg, msg['event']))
                    t.start()
                    self._cb_threads.add(t)

                # occasionally join cb threads
                for t in tuple(self._cb_threads):
                    t.join(0)
                    if not t.is_alive():
                        self._cb_threads.remove(t)
