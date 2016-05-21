# -*- coding: utf-8 -*-
'''
IPDB module
===========

Basically, IPDB is a transactional database, containing records,
that represent network stack objects. Any change in the database
is not reflected immediately in OS, but waits until `commit()`
is called. One failed operation during `commit()` rolls back all
the changes, has been made so far. Moreover, IPDB has commit
hooks API, that allows you to roll back changes depending on
your own function calls, e.g. when a host or a network becomes
unreachable.

IPDB vs. IPRoute
----------------

These two modules, IPRoute and IPDB, use completely different
approaches. The first one, IPRoute, just forward requests to
the kernel, and doesn't wait for the system state. So it's up
to developer to check, whether the requested object is really
set up, or not yet.

The latter, IPDB, is an asynchronously updated database, that
starts several additional threads by default. If your project's
policy doesn't allow implicit threads, keep it in mind. But
unlike IPRoute, the IPDB ensures the changes to be reflected
in the system::

    with IPDB() as ipdb:
        with ipdb.interfaces['eth0'] as i:
            i.up()
            i.add_ip('192.168.0.2/24')
            i.add_ip('192.168.0.3/24')
        # ---> <--- here you can expect `eth0` is up
        #           and has these two addresses, so
        #           the following code can rely on that

So IPDB is updated asynchronously, but the `commit()` operation
is synchronous.

NB: *In the example above `commit()` is implied with the
`__exit__()` of the `with` statement.*

The choice between IPDB and IPRoute depends on your project's
workflow. If you plan to retrieve the system info not too often
(or even once), or you are sure there will be not too many
network object, it is better to use IPRoute. If you plan to
lookup the network info on the regular basis and there can be
loads of network objects, it is better to use IPDB. Why?

IPRoute just loads what you ask -- and loads all the information
you ask to. While IPDB loads all the info upon startup, and
later is just updated by asynchronous broadcast netlink messages.
Assume you want to lookup ARP cache that contains hundreds or
even thousands of objects. Using IPRoute, you have to load all
the ARP cache every time you want to make a lookup. While IPDB
will load all the cache once, and then maintain it up-to-date
just inserting new records or removing them by one.

So, IPRoute is much simpler when you need to make a call and
then exit, while IPDB is cheaper in terms of CPU performance
if you implement a long-running program like a daemon.

Quickstart
----------

Simple tutorial::

    from pyroute2 import IPDB
    # several IPDB instances are supported within on process
    ipdb = IPDB()

    # commit is called automatically upon the exit from `with`
    # statement
    with ipdb.interfaces.eth0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'bala'
        i.txqlen = 2000

    # basic routing support
    ipdb.routes.add({'dst': 'default',
                     'gateway': '10.0.0.1'}).commit()

    # do not forget to shutdown IPDB
    ipdb.release()

Please, notice `ip.release()` call in the end. Though it is
not forced in an interactive python session for the better
user experience, it is required in the scripts to sync the
IPDB state before exit.

IPDB supports functional-like syntax also::

    from pyroute2 import IPDB
    with IPDB() as ipdb:
        intf = (ipdb.interfaces['eth0']
                .add_ip('10.0.0.2/24')
                .add_ip('10.0.0.3/24')
                .set_address('00:11:22:33:44:55')
                .set_mtu(1460)
                .set_name('external')
                .commit())
        # ---> <--- here you have the interface reference with
        #           all the changes applied: renamed, added ipaddr,
        #           changed macaddr and mtu.
        ...  # some code

    # pls notice, that the interface reference will not work
    # outside of `with IPDB() ...`

Transaction modes
-----------------
IPDB has several operating modes:

    - 'implicit' (default) -- the first change starts an implicit
        transaction, that have to be committed
    - 'explicit' -- you have to begin() a transaction prior to
        make any change

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


Note, that you can `review()` the `current_tx` transaction, and
`commit()` or `drop()` it. Also, multiple transactions are
supported, use uuid returned by `begin()` to identify them.

Actually, the form like 'ip.tap0.address' is an eye-candy. The
IPDB objects are dictionaries, so you can write the code above
as that::

    ipdb.interfaces['tap0'].down()
    ipdb.interfaces['tap0']['address'] = '00:11:22:33:44:55'
    ...

Context managers
----------------

Transactional objects (interfaces, routes) can act as context
managers in the same way as IPDB does itself::

    with ipdb.interfaces.tap0 as i:
        i.address = '00:11:22:33:44:55'
        i.ifname = 'vpn'
        i.add_ip('10.0.0.1', 24)
        i.add_ip('10.0.0.1', 24)

On exit, the context manager will authomatically `commit()` the
transaction.

Create interfaces
-----------------

IPDB can also create virtual interfaces::

    with ipdb.create(kind='bridge', ifname='control') as i:
        i.add_port(ip.interfaces.eth1)
        i.add_port(ip.interfaces.eth2)
        i.add_ip('10.0.0.1/24')


The `IPDB.create()` call has the same syntax as `IPRoute.link('add', ...)`,
except you shouldn't specify the `'add'` command. Refer to `IPRoute` docs
for details.

Routes management
-----------------

IPDB has a simple yet useful routing management interface.
To add a route, there is an easy to use syntax::

    # spec as a dictionary
    spec = {'dst': '172.16.1.0/24',
            'oif': 4,
            'gateway': '192.168.122.60',
            'metrics': {'mtu': 1400,
                        'advmss': 500}}

    # pass spec as is
    ipdb.routes.add(spec).commit()

    # pass spec as kwargs
    ipdb.routes.add(**spec).commit()

    # use keyword arguments explicitly
    ipdb.routes.add(dst='172.16.1.0/24', oif=4, ...).commit()

Please notice, that the device can be specified with `oif` (output
interface) or `iif` (input interface), the `device` keyword is not
supported anymore.

To access and change the routes, one can use notations as follows::

    # default table (254)
    #
    # change the route gateway and mtu
    #
    with ipdb.routes['172.16.1.0/24'] as route:
        route.gateway = '192.168.122.60'
        route.metrics.mtu = 1500

    # access the default route
    print(ipdb.routes['default])

    # change the default gateway
    with ipdb.routes['default'] as route:
        route.gateway = '10.0.0.1'

    # list automatic routes keys
    print(ipdb.routes.tables[255].keys())

Route specs
~~~~~~~~~~~

It is important to understand, that routing tables in IPDB
are lists, not dicts. It is still possible to use a dict syntax
to retrieve records, but under the hood the tables are lists.

To retrieve or create routes one should use route specs. The
simplest case is to retrieve one route::

    # get route by prefix
    ipdb.routes['172.16.1.0/24']

    # get route by a special name
    ipdb.routes['default']

If there are more than one route that matches the spec, only
the first one will be retrieved. One should iterate all the
records and filter by a key to retrieve all matches::

    # only one route will be retrieved
    ipdb.routes['fe80::/64']

    # get all routes by this prefix
    [ x for x in ipdb.routes if x['dst'] == 'fe80::/64' ]

It is possible to use dicts as specs::

    ipdb.routes[{'dst': '172.16.0.0/16',
                 'oif': 2}]

The dict is just the same as a route representation in the
records list.

Route metrics
~~~~~~~~~~~~~

A special object is dedicated to route metrics, one can access it
via `route.metrics` or `route['metrics']`::

    # these two statements are equal:
    with ipdb.routes['172.16.1.0/24'] as route:
        route['metrics']['mtu'] = 1400

    with ipdb.routes['172.16.1.0/24'] as route:
        route.metrics.mtu = 1400

Possible metrics are defined in `rtmsg.py:rtmsg.metrics`, e.g.
`RTAX_HOPLIMIT` means `hoplimit` metric etc.

Multipath routing
~~~~~~~~~~~~~~~~~

Multipath nexthops are managed via `route.add_nh()` and `route.del_nh()`
methods. They are available to review via `route.multipath`, but one
should not directly add/remove/modify nexthops in `route.multipath`, as
the changes will not be committed correctly.

To create a multipath route::

    ipdb.routes.add({'dst': '172.16.232.0/24',
                     'multipath': [{'gateway': '172.16.231.2',
                                    'hops': 2},
                                   {'gateway': '172.16.231.3',
                                    'hops': 1},
                                   {'gateway': '172.16.231.4'}]}).commit()

To change a multipath route::

    with ipdb.routes['172.16.232.0/24'] as r:
        r.add_nh({'gateway': '172.16.231.5'})
        r.del_nh({'gateway': '172.16.231.4'})

Another possible way is to create a normal route and turn it into
multipath by `add_nh()`::

    # create a non-MP route with one gateway:
    (ipdb
     .routes
     .add({'dst': '172.16.232.0/24',
           'gateway': '172.16.231.2'})
     .commit())

    # turn it to become a MP route:
    (ipdb
     .routes['172.16.232.0/24']
     .add_nh({'gateway': '172.16.231.3'})
     .commit())

    # here the route will contain two NH records, with
    # gateways 172.16.231.2 and 172.16.231.3

    # remove one NH and turn the route to be a normal one
    (ipdb
     .routes['172.16.232.0/24']
     .del_nh({'gateway': '172.16.231.2'})
     .commit())

    # thereafter the traffic to 172.16.232.0/24 will go only
    # via 172.16.231.3

Differences from the iproute2 syntax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By historical reasons, `iproute2` uses names that differs from what
the kernel uses. E.g., `iproute2` uses `weight` for multipath route
hops instead of `hops`, where `weight == (hops + 1)`. Thus, a route
created with `hops == 2` will be listed by `iproute2` as `weight 3`.

Another significant difference is `metrics`. The `pyroute2` library
uses the kernel naming scheme, where `metrics` means mtu, rtt, window
etc. The `iproute2` utility uses `metric` (not `metrics`) as a name
for the `priority` field.

In examples::

    # -------------------------------------------------------
    # iproute2 command:
    $ ip route add default \\
        nexthop via 172.16.0.1 weight 2 \\
        nexthop via 172.16.0.2 weight 9

    # pyroute2 code:
    (ipdb
     .routes
     .add({'dst': 'default',
           'multipath': [{'gateway': '172.16.0.1', 'hops': 1},
                         {'gateway': '172.16.0.2', 'hops': 8}])
     .commit())

    # -------------------------------------------------------
    # iproute2 command:
    $ ip route add default via 172.16.0.2 metric 200

    # pyroute2 code:
    (ipdb
     .routes
     .add({'dst': 'default',
           'gateway': '172.16.0.2',
           'priority': 200})
     .commit())

    # -------------------------------------------------------
    # iproute2 command:
    $ ip route add default via 172.16.0.2 mtu 1460

    # pyroute2 code:
    (ipdb
     .routes
     .add({'dst': 'default',
           'gateway': '172.16.0.2',
           'metrics': {'mtu': 1460}})
     .commit())

Multipath default routes
~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::
    As of the merge of kill_rtcache into the kernel, and it's
    release in ~3.6, weighted default routes no longer work in
    Linux.

Please refer to
https://github.com/svinota/pyroute2/issues/171#issuecomment-149297244
for details.

Performance issues
------------------

In the case of bursts of Netlink broadcast messages, all
the activity of the pyroute2-based code in the async mode
becomes suppressed to leave more CPU resources to the
packet reader thread. So please be ready to cope with
delays in the case of Netlink broadcast storms. It means
also, that IPDB state will be synchronized with OS also
after some delay.

The class API
-------------
'''
import atexit
import logging
import traceback
import threading

from socket import AF_INET
from socket import AF_INET6
from socket import AF_BRIDGE
from pyroute2 import config
from pyroute2.config import TransactionalBase
from pyroute2.common import View
from pyroute2.common import basestring
from pyroute2.common import uuid32
from pyroute2.common import AF_MPLS
from pyroute2.iproute import IPRoute
from pyroute2.netlink.rtnl import RTM_GETLINK
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.ipdb.route import RoutingTableSet
from pyroute2.ipdb.interface import Interface
from pyroute2.ipdb.linkedset import LinkedSet
from pyroute2.ipdb.linkedset import IPaddrSet
from pyroute2.ipdb.exceptions import CreateException
from pyroute2.ipdb.transactional import SYNC_TIMEOUT

logging.basicConfig()
log = logging.getLogger(__name__)


def get_addr_nla(msg):
    ###
    # Utility function to get NLA, containing the interface
    # address.
    #
    # Inconsistency in Linux IP addressing scheme is that
    # IPv4 uses IFA_LOCAL to store interface's ip address,
    # and IPv6 uses for the same IFA_ADDRESS.
    #
    # IPv4 sets IFA_ADDRESS to == IFA_LOCAL or to a
    # tunneling endpoint.
    #
    # Args:
    #     - msg (nlmsg): RTM\_.*ADDR message
    #
    # Returns:
    #     - nla (nla): IFA_LOCAL for IPv4 and IFA_ADDRESS for IPv6
    ###
    nla = None
    if msg['family'] == AF_INET:
        nla = msg.get_attr('IFA_LOCAL')
    elif msg['family'] == AF_INET6:
        nla = msg.get_attr('IFA_ADDRESS')
    return nla


class Watchdog(object):
    def __init__(self, ipdb, action, kwarg):
        self.event = threading.Event()
        self.is_set = False
        self.ipdb = ipdb

        def cb(ipdb, msg, _action):
            if _action != action:
                return

            for key in kwarg:
                if (msg.get(key, None) != kwarg[key]) and \
                        (msg.get_attr(msg.name2nla(key)) != kwarg[key]):
                    return

            self.is_set = True
            self.event.set()
        self.cb = cb
        # register callback prior to other things
        self.uuid = self.ipdb.register_callback(self.cb)

    def wait(self, timeout=SYNC_TIMEOUT):
        ret = self.event.wait(timeout=timeout)
        self.cancel()
        return ret

    def cancel(self):
        self.ipdb.unregister_callback(self.uuid)


class IPDB(object):
    '''
    The class that maintains information about network setup
    of the host. Monitoring netlink events allows it to react
    immediately. It uses no polling.
    '''

    def __init__(self, nl=None, mode='implicit',
                 restart_on_error=None, nl_async=None,
                 debug=False, ignore_rtables=None):
        self.mode = mode
        self.debug = debug
        if isinstance(ignore_rtables, int):
            self._ignore_rtables = [ignore_rtables, ]
        elif isinstance(ignore_rtables, (list, tuple, set)):
            self._ignore_rtables = ignore_rtables
        else:
            self._ignore_rtables = []
        self.iclass = Interface
        self._nl_async = config.ipdb_nl_async if nl_async is None else True
        self._stop = False
        # see also 'register_callback'
        self._post_callbacks = {}
        self._pre_callbacks = {}
        self._cb_threads = {}

        # locks and events
        self.exclusive = threading.RLock()
        self._shutdown_lock = threading.Lock()

        # load information
        self.restart_on_error = restart_on_error if \
            restart_on_error is not None else nl is None
        self.initdb(nl)

        # start monitoring thread
        self._mthread = threading.Thread(target=self.serve_forever)
        self._mthread.setDaemon(True)
        self._mthread.start()
        #
        atexit.register(self.release)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def initdb(self, nl=None):
        self.nl = nl or IPRoute()
        self.mnl = self.nl.clone()

        # resolvers
        self.interfaces = TransactionalBase()
        self.routes = RoutingTableSet(ipdb=self,
                                      ignore_rtables=self._ignore_rtables)
        self.by_name = View(src=self.interfaces,
                            constraint=lambda k, v: isinstance(k, basestring))
        self.by_index = View(src=self.interfaces,
                             constraint=lambda k, v: isinstance(k, int))

        # caches
        self.ipaddr = {}
        self.neighbours = {}

        try:
            self.mnl.bind(async=self._nl_async)
            # load information
            links = self.nl.get_links()
            for link in links:
                self._interface_add(link, skip_slaves=True)
            for link in links:
                self.update_slaves(link)
            # bridge info
            links = self.nl.get_vlans()
            for link in links:
                self._interface_add(link)
            #
            for msg in self.nl.get_addr():
                self._addr_add(msg)
            for msg in self.nl.get_neighbours():
                self._neigh_add(msg)
            for msg in self.nl.get_routes(family=AF_INET):
                self._route_add(msg)
            for msg in self.nl.get_routes(family=AF_INET6):
                self._route_add(msg)
            for msg in self.nl.get_routes(family=AF_MPLS):
                self._route_add(msg)
        except Exception as e:
            log.error('initdb error: %s', e)
            log.error(traceback.format_exc())
            try:
                self.nl.close()
                self.mnl.close()
            except:
                pass
            raise e

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
            - callback function
            - mode (optional, default="post")

        The callback should be a routine, that accepts three
        arguments::

            cb(ipdb, msg, action)

        Arguments are:

            - **ipdb** is a reference to IPDB instance, that invokes
                the callback.
            - **msg** is a message arrived
            - **action** is just a msg['event'] field

        E.g., to work on a new interface, you should catch
        action == 'RTM_NEWLINK' and with the interface index
        (arrived in msg['index']) get it from IPDB::

            index = msg['index']
            interface = ipdb.interfaces[index]
        '''
        lock = threading.Lock()

        def safe(*argv, **kwarg):
            with lock:
                callback(*argv, **kwarg)

        safe.hook = callback
        safe.lock = lock
        safe.uuid = uuid32()

        if mode == 'post':
            self._post_callbacks[safe.uuid] = safe
        elif mode == 'pre':
            self._pre_callbacks[safe.uuid] = safe
        return safe.uuid

    def unregister_callback(self, cuid, mode='post'):
        if mode == 'post':
            cbchain = self._post_callbacks
        elif mode == 'pre':
            cbchain = self._pre_callbacks
        else:
            raise KeyError('Unknown callback mode')
        safe = cbchain[cuid]
        with safe.lock:
            cbchain.pop(cuid)
        for t in tuple(self._cb_threads.get(cuid, ())):
            t.join(3)
        ret = self._cb_threads.get(cuid, ())
        return ret

    def release(self):
        '''
        Shutdown IPDB instance and sync the state. Since
        IPDB is asyncronous, some operations continue in the
        background, e.g. callbacks. So, prior to exit the
        script, it is required to properly shutdown IPDB.

        The shutdown sequence is not forced in an interactive
        python session, since it is easier for users and there
        is enough time to sync the state. But for the scripts
        the `release()` call is required.
        '''
        with self._shutdown_lock:
            if self._stop:
                return
            self._stop = True
            # terminate the main loop
            for t in range(3):
                try:
                    msg = ifinfmsg()
                    msg['index'] = 1
                    msg.reset()
                    self.mnl.put(msg, RTM_GETLINK)
                except Exception as e:
                    logging.warning("shotdown error: %s", e)
                    # Just give up.
                    # We can not handle this case

            self._mthread.join()
            self.nl.close()
            self.nl = None
            self.mnl.close()
            self.mnl = None

        with self.exclusive:
                # collect all the callbacks
                for cuid in tuple(self._cb_threads):
                    for t in tuple(self._cb_threads[cuid]):
                        t.join()
                # flush all the objects
                for (key, dev) in self.by_name.items():
                    try:
                        self.detach(key, dev['index'], dev.nlmsg)
                    except KeyError:
                        pass

                def flush(idx):
                    for key in tuple(idx.keys()):
                        try:
                            del idx[key]
                        except KeyError:
                            pass
                idx_list = [self.routes.tables[x] for x
                            in self.routes.tables.keys()]
                idx_list.append(self.ipaddr)
                idx_list.append(self.neighbours)
                for idx in idx_list:
                    flush(idx)

    def create(self, kind, ifname, reuse=False, **kwarg):
        with self.exclusive:
            # check for existing interface
            if ifname in self.interfaces:
                if (self.interfaces[ifname]['ipdb_scope'] == 'shadow') \
                        or reuse:
                    device = self.interfaces[ifname]
                    kwarg['kind'] = kind
                    device.load_dict(kwarg)
                    if self.interfaces[ifname]['ipdb_scope'] == 'shadow':
                        with device._direct_state:
                            device['ipdb_scope'] = 'create'
                else:
                    raise CreateException("interface %s exists" %
                                          ifname)
            else:
                device = \
                    self.interfaces[ifname] = \
                    self.iclass(ipdb=self, mode='snapshot')
                device.update(kwarg)
                if isinstance(kwarg.get('link', None), Interface):
                    device['link'] = kwarg['link']['index']
                if isinstance(kwarg.get('vxlan_link', None), Interface):
                    device['vxlan_link'] = kwarg['vxlan_link']['index']
                device['kind'] = kind
                device['index'] = kwarg.get('index', 0)
                device['ifname'] = ifname
                device['ipdb_scope'] = 'create'
                device._mode = self.mode
            device.begin()
        return device

    def commit(self, transactions=None, rollback=False):
        # what to commit: either from transactions argument, or from
        # started transactions on existing objects
        if transactions is None:
            # collect interface transactions
            txlist = [(x, x.current_tx) for x
                      in self.by_name.values() if x.local_tx.values()]
            # collect route transactions
            for table in self.routes.tables.keys():
                txlist.extend([(x, x.current_tx) for x in
                               self.routes.tables[table]
                               if x.local_tx.values()])
            txlist = sorted(txlist,
                            key=lambda x: x[1]['ipdb_priority'],
                            reverse=True)
            transactions = txlist

        snapshots = []
        removed = []

        try:
            for (target, tx) in transactions:
                if target['ipdb_scope'] == 'detached':
                    continue
                if tx['ipdb_scope'] == 'remove':
                    tx['ipdb_scope'] = 'shadow'
                    removed.append((target, tx))
                if not rollback:
                    s = (target, target.pick(detached=True))
                    snapshots.append(s)
                target.commit(transaction=tx, rollback=rollback)
        except Exception:
            if not rollback:
                self.fallen = transactions
                self.commit(transactions=snapshots, rollback=True)
            raise
        else:
            if not rollback:
                for (target, tx) in removed:
                    target['ipdb_scope'] = 'detached'
                    target.detach()
        finally:
            if not rollback:
                for (target, tx) in transactions:
                    target.drop(tx.uid)

    def _interface_del(self, msg):
        target = self.interfaces.get(msg['index'])
        if target is None:
            return
        for record in self.routes.filter({'oif': msg['index']}):
            with record['route']._direct_state:
                record['route']['ipdb_scope'] = 'gc'
        for record in self.routes.filter({'iif': msg['index']}):
            with record['route']._direct_state:
                record['route']['ipdb_scope'] = 'gc'
        target.nlmsg = msg
        # check for freezed devices
        if getattr(target, '_freeze', None):
            with target._direct_state:
                target['ipdb_scope'] = 'shadow'
            return
        # check for locked devices
        if target.get('ipdb_scope') in ('locked', 'shadow'):
            return
        self.detach(None, msg['index'], msg)

    def _interface_add(self, msg, skip_slaves=False):
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
            device = \
                self.interfaces[index] = \
                self.interfaces[ifname] = self.iclass(ipdb=self)
        elif ((index not in self.interfaces) and
                (ifname in self.interfaces)):
            # scenario #2, index change
            old_index = self.interfaces[ifname]['index']
            device = self.interfaces[index] = self.interfaces[ifname]
            if old_index in self.interfaces:
                del self.interfaces[old_index]
            if old_index in self.ipaddr:
                self.ipaddr[index] = self.ipaddr[old_index]
                del self.ipaddr[old_index]
            if old_index in self.neighbours:
                self.neighbours[index] = self.neighbours[old_index]
                del self.neighbours[old_index]
        else:
            # scenario #3, interface rename
            # scenario #4, assume rename
            old_name = self.interfaces[index]['ifname']
            if old_name != ifname:
                # unlink old name
                del self.interfaces[old_name]
            device = self.interfaces[ifname] = self.interfaces[index]

        if index not in self.ipaddr:
            # for interfaces, created by IPDB
            self.ipaddr[index] = IPaddrSet()

        if index not in self.neighbours:
            self.neighbours[index] = LinkedSet()

        device.load_netlink(msg)

        if not skip_slaves:
            self.update_slaves(msg)

    def detach(self, name, idx, msg=None):
        with self.exclusive:
            if msg is not None:
                try:
                    self.update_slaves(msg)
                except KeyError:
                    pass
                if msg['event'] == 'RTM_DELLINK' and \
                        msg['change'] != 0xffffffff:
                    return
            if idx is None or idx < 1:
                target = self.interfaces[name]
                idx = target['index']
            else:
                target = self.interfaces[idx]
                name = target['ifname']
            self.interfaces.pop(name, None)
            self.interfaces.pop(idx, None)
            self.ipaddr.pop(idx, None)
            self.neighbours.pop(idx, None)
            with target._direct_state:
                target['ipdb_scope'] = 'detached'

    def watchdog(self, action='RTM_NEWLINK', **kwarg):
        return Watchdog(self, action, kwarg)

    def _route_add(self, msg):
        self.routes.load_netlink(msg)

    def _route_del(self, msg):
        self.routes.load_netlink(msg)

    def update_slaves(self, msg):
        # Update slaves list -- only after update IPDB!

        index = msg['index']
        master_index = msg.get_attr('IFLA_MASTER')
        if index == master_index:
            # one special case: links() call with AF_BRIDGE
            # returns IFLA_MASTER == index
            return
        master = self.interfaces.get(master_index, None)
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
                        try:
                            with self.interfaces[device]._direct_state:
                                self.interfaces[device].del_port(index)
                        except KeyError:
                            pass
                with master._direct_state:
                    master.add_port(index)
            elif msg['event'] == 'RTM_DELLINK':
                if index in master['ports']:
                    with master._direct_state:
                        master.del_port(index)
        # there is NO masters for the interface, clean them if any
        else:
            device = self.interfaces[msg['index']]
            # clean vlan list from the port
            for vlan in tuple(device['vlans']):
                with device._direct_state:
                    device.del_vlan(vlan)
            # clean device from ports
            for master in self.by_index:
                if index in self.interfaces[master]['ports']:
                    try:
                        with self.interfaces[master]._direct_state:
                            self.interfaces[master].del_port(index)
                    except KeyError:
                        pass
            master = device.if_master
            if master is not None:
                if 'master' in device:
                    with device._direct_state:
                        device['master'] = None
                if (master in self.interfaces) and \
                        (msg['index'] in self.interfaces[master]['ports']):
                    try:
                        with self.interfaces[master]._direct_state:
                            self.interfaces[master].del_port(index)
                    except KeyError:
                        pass

    def _addr_add(self, msg):
        if msg['family'] == AF_INET:
            addr = msg.get_attr('IFA_LOCAL')
        elif msg['family'] == AF_INET6:
            addr = msg.get_attr('IFA_ADDRESS')
        else:
            return
        raw = {'local': msg.get_attr('IFA_LOCAL'),
               'broadcast': msg.get_attr('IFA_BROADCAST'),
               'address': msg.get_attr('IFA_ADDRESS'),
               'flags': msg.get_attr('IFA_FLAGS'),
               'prefixlen': msg['prefixlen']}
        try:
            self.ipaddr[msg['index']].add(key=(addr, raw['prefixlen']),
                                          raw=raw)
        except:
            pass

    def _addr_del(self, msg):
        if msg['family'] == AF_INET:
            addr = msg.get_attr('IFA_LOCAL')
        elif msg['family'] == AF_INET6:
            addr = msg.get_attr('IFA_ADDRESS')
        else:
            return
        try:
            self.ipaddr[msg['index']].remove((addr, msg['prefixlen']))
        except:
            pass

    def _neigh_add(self, msg):
        if msg['family'] == AF_BRIDGE:
            return

        try:
            (self
             .neighbours[msg['ifindex']]
             .add(key=msg.get_attr('NDA_DST'),
                  raw={'lladdr': msg.get_attr('MDA_LLADDR')}))
        except:
            pass

    def _neigh_del(self, msg):
        if msg['family'] == AF_BRIDGE:
            return
        try:
            (self
             .neighbours[msg['ifindex']]
             .remove(msg.get_attr('NDA_DST')))
        except:
            pass

    def serve_forever(self):
        ###
        # Main monitoring cycle. It gets messages from the
        # default iproute queue and updates objects in the
        # database.
        #
        # Should not be called manually.
        ###
        event_map = {'RTM_NEWLINK': self._interface_add,
                     'RTM_DELLINK': self._interface_del,
                     'RTM_NEWADDR': self._addr_add,
                     'RTM_DELADDR': self._addr_del,
                     'RTM_NEWNEIGH': self._neigh_add,
                     'RTM_DELNEIGH': self._neigh_del,
                     'RTM_NEWROUTE': self._route_add,
                     'RTM_DELROUTE': self._route_del}
        while not self._stop:
            try:
                messages = self.mnl.get()
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
                log.error('Restarting IPDB instance after '
                          'error:\n%s', traceback.format_exc())
                if self.restart_on_error:
                    try:
                        self.initdb()
                    except:
                        log.error('Error restarting DB:\n%s',
                                  traceback.format_exc())
                        return
                    continue
                else:
                    raise RuntimeError('Emergency shutdown')
            for msg in messages:
                # Run pre-callbacks
                # NOTE: pre-callbacks are synchronous
                for (cuid, cb) in tuple(self._pre_callbacks.items()):
                    try:
                        cb(self, msg, msg['event'])
                    except:
                        pass

                with self.exclusive:
                    event = msg.get('event', None)
                    if event in event_map:
                        event_map[event](msg)

                # run post-callbacks
                # NOTE: post-callbacks are asynchronous
                for (cuid, cb) in tuple(self._post_callbacks.items()):
                    t = threading.Thread(name="callback %s" % (id(cb)),
                                         target=cb,
                                         args=(self, msg, msg['event']))
                    t.start()
                    if cuid not in self._cb_threads:
                        self._cb_threads[cuid] = set()
                    self._cb_threads[cuid].add(t)

                # occasionally join cb threads
                for cuid in tuple(self._cb_threads):
                    for t in tuple(self._cb_threads.get(cuid, ())):
                        t.join(0)
                        if not t.is_alive():
                            try:
                                self._cb_threads[cuid].remove(t)
                            except KeyError:
                                pass
                            if len(self._cb_threads.get(cuid, ())) == 0:
                                del self._cb_threads[cuid]
