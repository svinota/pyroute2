'''
IPDB module
===========

Basically, IPDB is a transactional database, containing records,
representing network stack objects. Any change in the database
is not reflected immediately in OS (unless you ask for that
explicitly), but waits until commit() is called.

quickstart
----------

Simple tutorial::

    from pyroute2 import IPDB
    # several IPDB instances are supported within on process
    ip = IPDB()

    # commit is called automatically upon the exit from `with`
    # statement
    with ip.interfaces.eth0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'bala'
        i.txqlen = 2000

    # basic routing support
    ip.routes.add({'dst': 'default', 'gateway': '10.0.0.1'}).commit()

IPDB uses IPRoute as a transport, and monitors all broadcast
netlink messages from the kernel, thus keeping the database
up-to-date in an asynchronous manner. IPDB inherits `dict`
class, and has two keys::

    >>> from pyroute2 import IPDB
    >>> ip = IPDB()
    >>> ip.by_name.keys()
    ['bond0', 'lo', 'em1', 'wlan0', 'dummy0', 'virbr0-nic', 'virbr0']
    >>> ip.by_index.keys()
    [32, 1, 2, 3, 4, 5, 8]
    >>> ip.interfaces.keys()
    [32,
     1,
     2,
     3,
     4,
     5,
     8,
     'lo',
     'em1',
     'wlan0',
     'bond0',
     'dummy0',
     'virbr0-nic',
     'virbr0']
    >>> ip.interfaces['em1']['address']
    'f0:de:f1:93:94:0d'
    >>> ip.interfaces['em1']['ipaddr']
    [('10.34.131.210', 23),
     ('2620:52:0:2282:f2de:f1ff:fe93:940d', 64),
     ('fe80::f2de:f1ff:fe93:940d', 64)]
    >>>

One can address objects in IPDB not only with dict notation, but
with dot notation also:

    >>> ip.interfaces.em1.address
    'f0:de:f1:93:94:0d'
    >>> ip.interfaces.em1.ipaddr
    [('10.34.131.210', 23),
     ('2620:52:0:2282:f2de:f1ff:fe93:940d', 64),
     ('fe80::f2de:f1ff:fe93:940d', 64)]
    ```

It is up to you, which way to choose. The former, being more flexible,
is better for developers, the latter, the shorter form -- for system
administrators.


The library has also IPDB module. It is a database synchronized with
the kernel, containing some of the information. It can be used also
to set up IP settings in a transactional manner:

    >>> from pyroute2 import IPDB
    >>> from pprint import pprint
    >>> ip = IPDB()
    >>> pprint(ip.by_name.keys())
    ['bond0',
     'lo',
     'vnet0',
     'em1',
     'wlan0',
     'macvtap0',
     'dummy0',
     'virbr0-nic',
     'virbr0']
    >>> ip.interfaces.lo
    {'promiscuity': 0,
     'operstate': 'UNKNOWN',
     'qdisc': 'noqueue',
     'group': 0,
     'family': 0,
     'index': 1,
     'linkmode': 0,
     'ipaddr': [('127.0.0.1', 8), ('::1', 128)],
     'mtu': 65536,
     'broadcast': '00:00:00:00:00:00',
     'num_rx_queues': 1,
     'txqlen': 0,
     'ifi_type': 772,
     'address': '00:00:00:00:00:00',
     'flags': 65609,
     'ifname': 'lo',
     'num_tx_queues': 1,
     'ports': [],
     'change': 0}
    >>>

transaction modes
-----------------
IPDB has several operating modes:

 * 'direct' -- any change goes immediately to the OS level
 * 'implicit' (default) -- the first change starts an implicit
   transaction, that have to be committed
 * 'explicit' -- you have to begin() a transaction prior to
   make any change
 * 'snapshot' -- no changes will go to the OS in any case

The default is to use implicit transaction. This behaviour can
be changed in the future, so use 'mode' argument when creating
IPDB instances.

The sample session with explicit transactions::

    In [1]: from pyroute2 import IPDB
    In [2]: ip = IPDB(mode='explicit')
    In [3]: ifdb = ip.interfaces
    In [4]: ifdb.tap0.begin()
        Out[3]: UUID('7a637a44-8935-4395-b5e7-0ce40d31d937')
    In [5]: ifdb.tap0.up()
    In [6]: ifdb.tap0.address = '00:11:22:33:44:55'
    In [7]: ifdb.tap0.add_ip('10.0.0.1', 24)
    In [8]: ifdb.tap0.add_ip('10.0.0.2', 24)
    In [9]: ifdb.tap0.review()
        Out[8]:
        {'+ipaddr': set([('10.0.0.2', 24), ('10.0.0.1', 24)]),
         '-ipaddr': set([]),
         'address': '00:11:22:33:44:55',
         'flags': 4099}
    In [10]: ifdb.tap0.commit()


Note, that you can `review()` the `last()` transaction, and
`commit()` or `drop()` it. Also, multiple `self._transactions`
are supported, use uuid returned by `begin()` to identify them.

Actually, the form like 'ip.tap0.address' is an eye-candy. The
IPDB objects are dictionaries, so you can write the code above
as that::

    ip.interfaces['tap0'].down()
    ip.interfaces['tap0']['address'] = '00:11:22:33:44:55'
    ...

context managers
----------------

Also, interface objects in transactional mode can operate as
context managers::

    with ip.interfaces.tap0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'vpn'
        i.add_ip('10.0.0.1', 24)
        i.add_ip('10.0.0.1', 24)

On exit, the context manager will authomatically `commit()` the
transaction.

interface creation
------------------

IPDB can also create interfaces::

    with ip.create(kind='bridge', ifname='control') as i:
        i.add_port(ip.interfaces.eth1)
        i.add_port(ip.interfaces.eth2)
        i.add_ip('10.0.0.1/24')  # the same as i.add_ip('10.0.0.1', 24)

Right now IPDB supports creation of `dummy`, `bond`, `bridge`
and `vlan` interfaces. VLAN creation requires also `link` and
`vlan_id` parameters, see example scripts.

'''
import os
import sys
import time
import socket
import logging
import traceback
import threading

from socket import AF_UNSPEC
from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import dqn2int
from pyroute2.common import Dotkeys
from pyroute2.common import basestring
from pyroute2.common import ANCIENT
from pyroute2.netlink import NetlinkError
from pyroute2.iproute import IPRoute
from pyroute2.netlink.rtnl import RTM_GETLINK
from pyroute2.netlink.rtnl.req import BridgeRequest
from pyroute2.netlink.rtnl.req import BondRequest
from pyroute2.netlink.rtnl.req import IPLinkRequest
from pyroute2.netlink.rtnl.req import IPRouteRequest
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ifinfmsg import IFF_MASK
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.brmsg import brmsg
from pyroute2.netlink.rtnl.bomsg import bomsg
from pyroute2.ipdb.common import CreateException
from pyroute2.ipdb.common import CommitException
from pyroute2.ipdb.transactional import LinkedSet
from pyroute2.ipdb.transactional import update
from pyroute2.ipdb.transactional import Transactional


# How long should we wait on EACH commit() checkpoint: for ipaddr,
# ports etc. That's not total commit() timeout.
_SYNC_TIMEOUT = 5
_BARRIER = 0.2


def bypass(f):
    if ANCIENT:
        return f
    else:
        return lambda *x, **y: None


class compat(object):
    '''
    A namespace to keep all compat-related methods.
    '''
    @bypass
    @classmethod
    def fix_timeout(timeout):
        time.sleep(timeout)

    @bypass
    @classmethod
    def fix_check_link(nl, index):
        # check, if the link really exists --
        # on some old kernels you can receive
        # broadcast RTM_NEWLINK after the link
        # was deleted
        try:
            nl.get_links(index)
        except NetlinkError as e:
            if e.code == 19:  # No such device
                # just drop this message then
                return True


def get_interface_type(name):
    '''
    Utility function to get interface type.

    Unfortunately, we can not rely on RTNL or even ioctl().
    RHEL doesn't support interface type in RTNL and doesn't
    provide extended (private) interface flags via ioctl().

    Args:
        * name (str): interface name

    Returns:
        * False -- sysfs info unavailable
        * None -- type not known
        * str -- interface type:
            * 'bond'
            * 'bridge'
    '''
    # FIXME: support all interface types? Right now it is
    # not needed
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
    Utility function to get NLA, containing the interface
    address.

    Incosistency in Linux IP addressing scheme is that
    IPv4 uses IFA_LOCAL to store interface's ip address,
    and IPv6 uses for the same IFA_ADDRESS.

    IPv4 sets IFA_ADDRESS to == IFA_LOCAL or to a
    tunneling endpoint.

    Args:
        * msg (nlmsg): RTM\_.*ADDR message

    Returns:
        * nla (nla): IFA_LOCAL for IPv4 and IFA_ADDRESS for IPv6
    '''
    nla = None
    if msg['family'] == AF_INET:
        nla = msg.get_attr('IFA_LOCAL')
    elif msg['family'] == AF_INET6:
        nla = msg.get_attr('IFA_ADDRESS')
    return nla


class IPaddrSet(LinkedSet):
    '''
    LinkedSet child class with different target filter. The
    filter ignores link local IPv6 addresses when sets and checks
    the target.
    '''
    target_filter = lambda self, x: not ((x[0][:4] == 'fe80') and (x[1] == 64))


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
    _fields_cmp = {'flags': lambda x, y: x & y & IFF_MASK == y & IFF_MASK}

    def __init__(self, ipdb, mode=None):
        '''
        Parameters:
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
        self._flicker = False
        self._exception = None
        self._tb = None
        self._virtual_fields = ('removal', 'flicker', 'state')
        self._xfields = {'common': [ifinfmsg.nla2name(i[0]) for i
                                    in ifinfmsg.nla_map],
                         'bridge': [brmsg.nla2name(i[0]) for i
                                    in brmsg.commands.nla_map],
                         'bond': [bomsg.nla2name(i[0]) for i
                                  in bomsg.commands.nla_map]}
        self._xfields['bridge'].append('index')
        self._xfields['bond'].append('index')
        self._xfields['common'].append('index')
        self._xfields['common'].append('flags')
        self._xfields['common'].append('mask')
        self._xfields['common'].append('change')
        self._xfields['common'].append('kind')
        self._xfields['common'].append('vlan_id')
        self._xfields['common'].append('bond_mode')
        for ftype in self._xfields:
            self._fields += self._xfields[ftype]
        self._fields.extend(self._virtual_fields)
        self._load_event = threading.Event()
        self._linked_sets.add('ipaddr')
        self._linked_sets.add('ports')
        self._freeze = None
        # 8<-----------------------------------
        # local setup: direct state is required
        with self._direct_state:
            self['ipaddr'] = IPaddrSet()
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
        return self.get('master', None)

    def freeze(self):
        dump = self.dump()

        def cb(ipdb, msg, action):
            if msg.get('index', -1) == dump['index']:
                tr = self.load(dump)
                for _ in range(3):
                    try:
                        self.commit(transaction=tr)
                    except (CommitException, RuntimeError):
                        # ignore here both CommitExceptions
                        # and RuntimeErrors (aka rollback errors),
                        # since ususally it is a races between
                        # 3d party setup and freeze; just
                        # sliently try again for several times
                        continue
                    except NetlinkError:
                        # on the netlink errors just give up
                        pass
                    break

        self._freeze = cb
        self.ipdb.register_callback(self._freeze)
        return self

    def unfreeze(self):
        self.ipdb.unregister_callback(self._freeze)
        self._freeze = None
        return self

    def load(self, data):
        with self._write_lock:
            template = self.__class__(ipdb=self.ipdb, mode='snapshot')
            template.load_dict(data)
            return template

    def load_dict(self, data):
        with self._direct_state:
            for key in data:
                if key == 'ipaddr':
                    for addr in data[key]:
                        if isinstance(addr, basestring):
                            addr = (addr, )
                        self.add_ip(*addr)
                elif key == 'ports':
                    for port in data[key]:
                        self.add_port(port)
                else:
                    self[key] = data[key]

    def load_bridge(self):
        '''
        '''
        with self._direct_state:
            dev = self.nl.get_bridge(self['index'], self['ifname'])[0]
            attrs = dev.get_attr('IFBR_COMMANDS',
                                 {'attrs': []}).get('attrs', [])
            for (name, value) in [x[:2] for x in attrs]:
                norm = brmsg.nla2name(name)
                self[norm] = value

    def load_bond(self):
        '''
        '''
        with self._direct_state:
            dev = self.nl.get_bond(self['index'], self['ifname'])[0]
            attrs = dev.get_attr('IFBO_COMMANDS',
                                 {'attrs': []}).get('attrs', [])
            for (name, value) in [x[:2] for x in attrs]:
                norm = bomsg.nla2name(name)
                self[norm] = value

    def load_netlink(self, dev):
        '''
        Update the interface info from RTM_NEWLINK message.

        This call always bypasses open transactions, loading
        changes directly into the interface data.
        '''
        with self._direct_state:
            self._exists = True
            self.nlmsg = dev
            for (name, value) in dev.items():
                self[name] = value
            for item in dev['attrs']:
                name, value = item[:2]
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
            # poll bridge & bond info
            if self.get('kind', None) == 'bridge':
                self.load_bridge()
            elif self.get('kind', None) == 'bond':
                self.load_bond()
            # finally, cleanup all not needed
            for item in self.cleanup:
                if item in self:
                    del self[item]

            self.sync()

    def sync(self):
        self._load_event.set()

    @update
    def add_ip(self, direct, ip, mask=None):
        '''
        Add IP address to an interface
        '''
        # split mask
        if mask is None:
            ip, mask = ip.split('/')
            if mask.find('.') > -1:
                mask = dqn2int(mask)
            else:
                mask = int(mask, 0)
        # FIXME: make it more generic
        # skip IPv6 link-local addresses
        if ip[:4] == 'fe80' and mask == 64:
            return self
        if not direct:
            transaction = self.last()
            transaction.add_ip(ip, mask)
        else:
            self['ipaddr'].unlink((ip, mask))
            self['ipaddr'].add((ip, mask))
        return self

    @update
    def del_ip(self, direct, ip, mask=None):
        '''
        Delete IP address from an interface
        '''
        if mask is None:
            ip, mask = ip.split('/')
            if mask.find('.') > -1:
                mask = dqn2int(mask)
            else:
                mask = int(mask, 0)
        if not direct:
            transaction = self.last()
            if (ip, mask) in transaction['ipaddr']:
                transaction.del_ip(ip, mask)
        else:
            self['ipaddr'].unlink((ip, mask))
            self['ipaddr'].remove((ip, mask))
        return self

    @update
    def add_port(self, direct, port):
        '''
        Add a slave port to a bridge or bonding
        '''
        if isinstance(port, Interface):
            port = port['index']
        if not direct:
            transaction = self.last()
            transaction.add_port(port)
        else:
            self['ports'].unlink(port)
            self['ports'].add(port)
        return self

    @update
    def del_port(self, direct, port):
        '''
        Remove a slave port from a bridge or bonding
        '''
        if isinstance(port, Interface):
            port = port['index']
        if not direct:
            transaction = self.last()
            if port in transaction['ports']:
                transaction.del_port(port)
        else:
            self['ports'].unlink(port)
            self['ports'].remove(port)
        return self

    def reload(self):
        '''
        Reload interface information
        '''
        countdown = 3
        while countdown:
            links = self.nl.get_links(self['index'])
            if links:
                self.load_netlink(links[0])
                break
            else:
                countdown -= 1
                time.sleep(1)
        return self

    def filter(self, ftype):
        ret = {}
        for key in self:
            if key in self._xfields[ftype]:
                ret[key] = self[key]
        return ret

    def commit(self, tid=None, transaction=None, rollback=False):
        '''
        Commit transaction. In the case of exception all
        changes applied during commit will be reverted.
        '''
        error = None
        added = None
        removed = None
        drop = True
        if tid:
            transaction = self._transactions[tid]
        else:
            if transaction:
                drop = False
            else:
                transaction = self.last()

        wd = None
        with self._write_lock:
            # if the interface does not exist, create it first ;)
            if not self._exists:
                request = IPLinkRequest(self.filter('common'))

                # create watchdog
                wd = self.ipdb.watchdog(ifname=self['ifname'])

                try:
                    # 8<----------------------------------------------------
                    # ACHTUNG: hack for old platforms
                    if request.get('address', None) == '00:00:00:00:00:00':
                        del request['address']
                        del request['broadcast']
                    # 8<----------------------------------------------------
                    try:
                        self.nl.link('add', **request)
                    except NetlinkError as x:
                        # Operation not supported
                        if x.code == 95 and request.get('index', 0) != 0:
                            # ACHTUNG: hack for old platforms
                            request = IPLinkRequest({'ifname': self['ifname'],
                                                     'kind': self['kind'],
                                                     'index': 0})
                            self.nl.link('add', **request)
                        else:
                            raise
                except Exception as e:
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
                    self._exception = e
                    self._tb = traceback.format_exc()
                    # raise the exception
                    raise

        if wd is not None:
            wd.wait()

        # now we have our index and IP set and all other stuff
        snapshot = self.pick()

        try:
            removed = snapshot - transaction
            added = transaction - snapshot

            # 8<---------------------------------------------
            # IP address changes
            self['ipaddr'].set_target(transaction['ipaddr'])

            for i in removed['ipaddr']:
                # Ignore link-local IPv6 addresses
                if i[0][:4] == 'fe80' and i[1] == 64:
                    continue
                # When you remove a primary IP addr, all subnetwork
                # can be removed. In this case you will fail, but
                # it is OK, no need to roll back
                try:
                    self.nl.addr('delete', self['index'], i[0], i[1])
                except NetlinkError as x:
                    # bypass only errno 99, 'Cannot assign address'
                    if x.code != 99:
                        raise
                except socket.error as x:
                    # bypass illegal IP requests
                    if not x.args[0].startswith('illegal IP'):
                        raise

            for i in added['ipaddr']:
                # Ignore link-local IPv6 addresses
                if i[0][:4] == 'fe80' and i[1] == 64:
                    continue
                self.nl.addr('add', self['index'], i[0], i[1])

                # 8<--------------------------------------
                # FIXME: kernel bug, sometimes `addr add` for
                # bond interfaces returns success, but does
                # really nothing

                if self['kind'] == 'bond':
                    while True:
                        try:
                            # dirtiest hack, but we have to use it here
                            time.sleep(0.1)
                            self.nl.addr('add', self['index'], i[0], i[1])
                        # continue to try to add the address
                        # until the kernel reports `file exists`
                        #
                        # a stupid solution, but must help
                        except NetlinkError as e:
                            if e.code == 17:
                                break
                            else:
                                raise
                        except Exception:
                            raise
                # 8<--------------------------------------

            if removed['ipaddr'] or added['ipaddr']:
                # 8<--------------------------------------
                # bond and bridge interfaces do not send
                # IPv6 address updates, when are down
                #
                # beside of that, bridge interfaces are
                # down by default, so they never send
                # address updates from beginning
                #
                # so if we need, force address load
                #
                # FIXME: probably, we should handle other
                # types as well
                if self['kind'] in ('bond', 'bridge'):
                    self.nl.get_addr()
                # 8<--------------------------------------
                self['ipaddr'].target.wait(_SYNC_TIMEOUT)
                if not self['ipaddr'].target.is_set():
                    raise CommitException('ipaddr target is not set')

            # 8<---------------------------------------------
            # Interface slaves
            self['ports'].set_target(transaction['ports'])

            for i in removed['ports']:
                # detach the port
                port = self.ipdb.interfaces[i]
                port.set_target('master', None)
                port.mirror_target('master', 'link')
                self.nl.link('set', index=port['index'], master=0)

            for i in added['ports']:
                # enslave the port
                port = self.ipdb.interfaces[i]
                port.set_target('master', self['index'])
                port.mirror_target('master', 'link')
                self.nl.link('set',
                             index=port['index'],
                             master=self['index'])

            if removed['ports'] or added['ports']:
                self.nl.get_links(*(removed['ports'] | added['ports']))
                self['ports'].target.wait(_SYNC_TIMEOUT)
                if not self['ports'].target.is_set():
                    raise CommitException('ports target is not set')

                # RHEL 6.5 compat fix -- an explicit timeout
                # it gives a time for all the messages to pass
                compat.fix_timeout(1)

                # wait for proper targets on ports
                for i in list(added['ports']) + list(removed['ports']):
                    port = self.ipdb.interfaces[i]
                    target = port._local_targets['master']
                    target.wait(_SYNC_TIMEOUT)
                    del port._local_targets['master']
                    del port._local_targets['link']
                    if not target.is_set():
                        raise CommitException('master target failed')
                    if i in added['ports']:
                        assert port.if_master == self['index']
                    else:
                        assert port.if_master != self['index']

            # 8<---------------------------------------------
            # Interface changes
            request = IPLinkRequest()
            for key in added:
                if key in self._xfields['common']:
                    request[key] = added[key]
            request['index'] = self['index']

            # apply changes only if there is something to apply
            if any([request[item] is not None for item in request
                    if item != 'index']):
                self.nl.link('set', **request)

            # bridge changes
            if self['kind'] == 'bridge':
                brq = BridgeRequest()
                for key in added:
                    if key in self._xfields['bridge']:
                        brq[key] = added[key]

                brq['index'] = self['index']
                brq['ifname'] = self['ifname']
                self.nl.setbr(**brq)
                self.load_bridge()

            # bridge changes
            if self['kind'] == 'bond':
                boq = BondRequest()
                for key in added:
                    if key in self._xfields['bond']:
                        boq[key] = added[key]

                boq['index'] = self['index']
                boq['ifname'] = self['ifname']
                self.nl.setbo(**boq)
                self.load_bond()

            # reload interface to hit targets
            if transaction._targets:
                self.reload()

            # wait for targets
            for key, target in transaction._targets.items():
                if key not in self._virtual_fields:
                    target.wait(_SYNC_TIMEOUT)
                    if not target.is_set():
                        raise CommitException('target %s is not set' % key)

            # 8<---------------------------------------------
            # Interface removal
            if added.get('removal') or added.get('flicker'):
                wd = self.ipdb.watchdog(action='RTM_DELLINK',
                                        ifname=self['ifname'])
                if added.get('flicker'):
                    self._flicker = True
                self.nl.link('delete', **self)
                wd.wait()
                if added.get('flicker'):
                    self._exists = False
                if added.get('removal'):
                    self._mode = 'invalid'
                if drop:
                    self.drop(transaction)
                return self
            # 8<---------------------------------------------

            # Iterate callback chain
            for ch in self._commit_hooks:
                # An exception will rollback the transaction
                ch(self.dump(), snapshot.dump(), transaction.dump())
            # 8<---------------------------------------------

        except Exception as e:
            # something went wrong: roll the transaction back
            if not rollback:
                ret = self.commit(transaction=snapshot, rollback=True)
                # if some error was returned by the internal
                # closure, substitute the initial one
                if isinstance(ret, Exception):
                    error = ret
                else:
                    error = e
                    error.traceback = traceback.format_exc()
            elif isinstance(e, NetlinkError) and \
                    getattr(e, 'code', 0) == 1:
                # It is <Operation not permitted>, catched in
                # rollback. So return it -- see ~5 lines above
                e.traceback = traceback.format_exc()
                return e
            else:
                # somethig went wrong during automatic rollback.
                # that's the worst case, but it is still possible,
                # since we have no locks on OS level.
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
                x.traceback = traceback.format_exc()
                raise x

        # if it is not a rollback turn
        if drop and not rollback:
            # drop last transaction in any case
            self.drop(transaction)

        # raise exception for failed transaction
        if error is not None:
            error.transaction = transaction
            raise error

        time.sleep(_BARRIER)
        return self

    def up(self):
        '''
        Shortcut: change the interface state to 'up'.
        '''
        if self['flags'] is None:
            self['flags'] = 1
        else:
            self['flags'] |= 1
        return self

    def down(self):
        '''
        Shortcut: change the interface state to 'down'.
        '''
        if self['flags'] is None:
            self['flags'] = 0
        else:
            self['flags'] &= ~(self['flags'] & 1)
        return self

    def remove(self):
        '''
        Mark the interface for removal
        '''
        self['removal'] = True
        return self

    def shadow(self):
        '''
        Remove the interface from the OS, but leave it in the
        database. When one will try to re-create interface with
        the same name, all the old saved attributes will apply
        to the new interface, incl. MAC-address and even the
        interface index. Please be aware, that the interface
        index can be reused by OS while the interface is "in the
        shadow state", in this case re-creation will fail.
        '''
        self['flicker'] = True
        return self


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

    def load_netlink(self, msg):
        with self._direct_state:
            self._exists = True
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
        return self

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
                if isinstance(ret, Exception):
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

        return self

    def remove(self):
        self['removal'] = True
        return self


class RoutingTables(dict):

    def __init__(self, ipdb):
        dict.__init__(self)
        self.ipdb = ipdb
        self.tables = {254: {}}

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

    def load_netlink(self, msg):
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
            ret.load_netlink(msg)
        else:
            ret = Route(ipdb=self.ipdb)
            ret.load_netlink(msg)
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


class Watchdog(object):
    def __init__(self, ipdb, action, kwarg):
        self.event = threading.Event()
        self.ipdb = ipdb

        def cb(ipdb, msg, _action):
            if _action != action:
                return

            for key in kwarg:
                if (msg.get(key, None) != kwarg[key]) and \
                        (msg.get_attr(msg.name2nla(key)) != kwarg[key]):
                    return
            self.event.set()
        self.cb = cb
        # register callback prior to other things
        self.ipdb.register_callback(self.cb)

    def wait(self, timeout=_SYNC_TIMEOUT):
        self.event.wait(timeout=timeout)
        self.cancel()

    def cancel(self):
        self.ipdb.unregister_callback(self.cb)


class IPDB(object):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.
    '''

    def __init__(self, nl=None, mode='implicit', iclass=Interface):
        '''
        Parameters:
            * nl -- IPRoute() reference
            * mode -- (implicit, explicit, direct)
            * iclass -- the interface class type

        If you do not provide iproute instance, ipdb will
        start it automatically.
        '''
        self.nl = nl or IPRoute()
        self.nl.monitor = True
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
        self._mthread = threading.Thread(target=self.serve_forever)
        if hasattr(sys, 'ps1'):
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
                for t in tuple(self._cb_threads):
                    t.join(3)
                return cbchain.pop(cbchain.index(cb))

    def release(self):
        '''
        Shutdown monitoring thread and release iproute.
        '''
        self._stop = True
        self.nl.put({'index': 1}, RTM_GETLINK)
        self._mthread.join()
        self.nl.close()

    def create(self, kind, ifname, reuse=False, **kwarg):
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
        * reuse -- if such interface exists, return it anyway

        Different interface kinds can require different
        arguments for creation.

        FIXME: this should be documented.
        '''
        with self.exclusive:
            # check for existing interface
            if ifname in self.interfaces:
                if self.interfaces[ifname]._flicker or reuse:
                    device = self.interfaces[ifname]
                    device._flicker = False
                else:
                    raise CreateException("interface %s exists" %
                                          ifname)
            else:
                device = \
                    self.by_name[ifname] = \
                    self.interfaces[ifname] = \
                    self.iclass(ipdb=self, mode='snapshot')
                device.update(kwarg)
                if isinstance(kwarg.get('link', None), Interface):
                    device['link'] = kwarg['link']['index']
                device['kind'] = kind
                device['index'] = kwarg.get('index', 0)
                device['ifname'] = ifname
                device._mode = self.mode
            device.begin()
            return device

    def device_del(self, msg):
        # check for flicker devices
        if (msg.get('index', None) in self.interfaces) and \
                self.interfaces[msg['index']]._flicker:
            self.interfaces[msg['index']].sync()
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
            self.ipaddr[index] = IPaddrSet()

        device.load_netlink(msg)

        if not skip_slaves:
            self.update_slaves(msg)

    def detach(self, item):
        with self.exclusive:
            if item in self.interfaces:
                del self.interfaces[item]
            if item in self.by_name:
                del self.by_name[item]
            if item in self.by_index:
                del self.by_index[item]

    def watchdog(self, action='RTM_NEWLINK', **kwarg):
        return Watchdog(self, action, kwarg)

    def update_routes(self, routes):
        for msg in routes:
            self.routes.load_netlink(msg)

    def _lookup_master(self, msg):
        master = msg.get_attr('IFLA_MASTER')
        return self.interfaces.get(master, None)

    def update_slaves(self, msg):
        # Update slaves list -- only after update IPDB!

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
                if (master in self.interfaces) and \
                        (msg['index'] in self.interfaces[master].ports):
                    self.interfaces[master].del_port(msg['index'],
                                                     direct=True)

    def update_addr(self, addrs, action='add'):
        # Update address list of an interface.

        for addr in addrs:
            nla = get_addr_nla(addr)
            if nla is not None:
                try:
                    method = getattr(self.ipaddr[addr['index']], action)
                    method(key=(nla, addr['prefixlen']), raw=addr)
                except:
                    pass

    def serve_forever(self):
        '''
        Main monitoring cycle. It gets messages from the
        default iproute queue and updates objects in the
        database.

        .. note::
            Should not be called manually.
        '''
        while not self._stop:
            try:
                messages = self.nl.get()
                ##
                # Check it again
                #
                # NOTE: one should not run callbacks or
                # anything like that after setting the
                # _stop flag, since IPDB is not valid
                # anymore
                if self._stop:
                    break
            except:
                logging.warning(traceback.format_exc())
                time.sleep(3)
                continue
            for msg in messages:
                # Run pre-callbacks
                # NOTE: pre-callbacks are synchronous
                for cb in self._pre_callbacks:
                    try:
                        cb(self, msg, msg['event'])
                    except:
                        pass

                with self.exclusive:
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
