# -*- coding: utf-8 -*-
'''
IPDB module
===========

Basically, IPDB is a transactional database, containing
records, that represent network stack objects. Any change
in the database is not reflected immediately in OS, but
waits until `commit()` is called. One failed operation
during `commit()` rolls back all the changes, has been made
so far. Moreover, IPDB has commit hooks API, that allows
you to roll back changes depending on your own function
calls, e.g. when a host or a network becomes unreachable.

IPDB vs. IPRoute
----------------

These two modules, IPRoute and IPDB, use completely different
approaches. The first one, IPRoute, just forward requests to
the kernel, and doesn't wait for the system state. So it's up
to developer to check, whether the requested object is really
set up, or not yet.

The latter, IPDB, is an asynchronously updated database, that
starts several additional threads by default. If your
project's policy doesn't allow implicit threads, keep it in
mind. But unlike IPRoute, the IPDB ensures the changes to
be reflected in the system::

    with IPDB() as ipdb:
        with ipdb.interfaces['eth0'] as i:
            i.up()
            i.add_ip('192.168.0.2/24')
            i.add_ip('192.168.0.3/24')
        # ---> <--- here you can expect `eth0` is up
        #           and has these two addresses, so
        #           the following code can rely on that

So IPDB is updated asynchronously, but the `commit()`
operation is synchronous. At least, it is planned to be such.

NB: *In the example above `commit()` is implied with the
`__exit__()` of the `with` statement.*

The choice between IPDB and IPRoute depends on your project's
workflow. If you plan to retrieve the system info not too
often (or even once), or you are sure there will be not too
many network object, it is better to use IPRoute. If you
plan to lookup the network info on the regular basis and
there can be loads of network objects, it is better to use
IPDB. Why?

IPRoute just loads what you ask -- and loads all the
information you ask to. While IPDB loads all the info upon
startup, and later is just updated by asynchronous broadcast
netlink messages. Assume you want to lookup ARP cache that
contains hundreds or even thousands of objects. Using
IPRoute, you have to load all the ARP cache every time you
want to make a lookup. While IPDB will load all the cache
once, and then maintain it up-to-date just inserting new
records or removing them by one.

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

The default is to use implicit transaction. This behaviour
can be changed in the future, so use 'mode' argument when
creating IPDB instances.

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


Note, that you can `review()` the `current_tx` transaction,
and `commit()` or `drop()` it. Also, multiple transactions
are supported, use uuid returned by `begin()` to identify
them.

Actually, the form like 'ip.tap0.address' is an eye-candy.
The IPDB objects are dictionaries, so you can write the code
above as that::

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

On exit, the context manager will authomatically `commit()`
the transaction.

Create interfaces
-----------------

IPDB can also create virtual interfaces::

    with ipdb.create(kind='bridge', ifname='control') as i:
        i.add_port(ip.interfaces.eth1)
        i.add_port(ip.interfaces.eth2)
        i.add_ip('10.0.0.1/24')


The `IPDB.create()` call has the same syntax as
`IPRoute.link('add', ...)`, except you shouldn't specify
the `'add'` command. Refer to `IPRoute` docs for details.

Bridge interfaces
-----------------

Modern kernels provide possibility to manage bridge
interface properties such as STP, forward delay, ageing
time etc. Names of these properties start with `br_`, like
`br_ageing_time`, `br_forward_delay` e.g.::

    [x for x in dir(ipdb.interfaces.virbr0) if x.startswith('br_')]

Ports management
----------------

IPDB provides a uniform API to manage ports::

    with ipdb.interfaces['br-int'] as br:
        br.add_port('veth0')
        br.add_port(ipdb.interfaces.veth1)
        br.add_port(700)
        br.del_port('veth2')

Both `add_port()` and `del_port()` accept three types of arguments:

    * `'veth0'` -- interface name as a string
    * `ipdb.interfaces.veth1` -- IPDB interface object
    * `700` -- interface index, an integer

The same methods are used to manage bridge, bond and vrf ports.

Routes management
-----------------

IPDB has a simple yet useful routing management interface.

Create a route
~~~~~~~~~~~~~~

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

Please notice, that the device can be specified with `oif`
(output interface) or `iif` (input interface), the `device`
keyword is not supported anymore.

Get a route
~~~~~~~~~~~

To access and change the routes, one can use notations as
follows::

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

By default, the path `ipdb.routes` reflects only the main
routing table (254). But Linux supports much more routing
tables, so does IPDB::

    In [1]: ipdb.routes.tables.keys()
    Out[1]: [0, 254, 255]

    In [2]: len(ipdb.routes.tables[255])
    Out[2]: 11  # => 11 automatic routes in the table local

It is important to understand, that routing tables keys in
IPDB are not only the destination prefix. The key consists
of 'prefix/mask' string and the route priority (if any)::

    In [1]: ipdb.routes.tables[254].idx.keys()
    Out[1]:
    [RouteKey(dst='default', priority=600),
     RouteKey(dst='10.1.0.0/24', priority=600),
     RouteKey(dst='192.168.122.0/24', priority=None)]

But a routing table in IPDB allows several variants of the
route spec. The simplest case is to retrieve a route by
prefix, if there is only one match::

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

It is also possible to use dicts as specs::

    ipdb.routes[{'dst': '172.16.0.0/16',
                 'oif': 2}]

Route metrics
~~~~~~~~~~~~~

A special object is dedicated to route metrics, one can
access it via `route.metrics` or `route['metrics']`::

    # these two statements are equal:
    with ipdb.routes['172.16.1.0/24'] as route:
        route['metrics']['mtu'] = 1400

    with ipdb.routes['172.16.1.0/24'] as route:
        route.metrics.mtu = 1400

Possible metrics are defined in `rtmsg.py:rtmsg.metrics`,
e.g. `RTAX_HOPLIMIT` means `hoplimit` metric etc.

Multipath routing
~~~~~~~~~~~~~~~~~

Multipath nexthops are managed via `route.add_nh()` and
`route.del_nh()` methods. They are available to review via
`route.multipath`, but one should not directly
add/remove/modify nexthops in `route.multipath`, as the
changes will not be committed correctly.

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

Another possible way is to create a normal route and turn
it into multipath by `add_nh()`::

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

By historical reasons, `iproute2` uses names that differs
from what the kernel uses. E.g., `iproute2` uses `weight`
for multipath route hops instead of `hops`, where
`weight == (hops + 1)`. Thus, a route created with
`hops == 2` will be listed by `iproute2` as `weight 3`.

Another significant difference is `metrics`. The `pyroute2`
library uses the kernel naming scheme, where `metrics` means
mtu, rtt, window etc. The `iproute2` utility uses `metric`
(not `metrics`) as a name for the `priority` field.

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
    release in ~3.6, weighted default routes no longer work
    in Linux.

Please refer to
https://github.com/svinota/pyroute2/issues/171#issuecomment-149297244
for details.

Rules management
----------------

IPDB provides a basic IP rules management system.

Create a rule
~~~~~~~~~~~~~

Syntax is almost the same as for routes::

    # rule spec
    spec = {'src': '172.16.1.0/24',
            'table': 200,
            'priority': 15000}

    ipdb.rules.add(spec).commit()

Get a rule
~~~~~~~~~~

The way IPDB handles IP rules is almost the same as routes,
but rule keys are more complicated -- the Linux kernel
doesn't use keys for rules, but instead iterates all the
records until the first one w/o any attribute mismatch.

The fields that the kernel uses to compare rules, IPDB uses
as the key fields (see `pyroute2/ipdb/rule.py:RuleKey`)

There are also more ways to find a record, as with routes::

    # 1. iterate all the records
    for record in ipdb.rules:
        match(record)

    # 2. an integer as the key matches the first
    #    rule with that priority
    ipdb.rules[32565]

    # 3. a dict as the key returns the first match
    #    for all the specified attrs
    ipdb.rules[{'dst': '10.0.0.0/24', 'table': 200}]

Priorities
~~~~~~~~~~

Thus, the rule priority is **not** a key, neither in the
kernel, nor in IPDB. One should **not** rely on priorities
as on keys, there may be several rules with the same
priority, and it often happens, e.g. on Android systems.

Persistence
~~~~~~~~~~~

There is no *change* operation for the rule records in the
kernel, so only *add/del* work. When IPDB changes a record,
it effectively deletes the old one and creates the new with
new parameters, but the object, referring the record, stays
the same. Also that means, that IPDB can not recognize the
situation, when someone else does the same. So if there is
another program changing records by *del/add* operations,
even another IPDB instance, referring objects in the IPDB
will be recreated.

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

from pyroute2 import config
from pyroute2.common import uuid32
from pyroute2.iproute import IPRoute
from pyroute2.netlink.rtnl import RTM_GETLINK
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.ipdb import rule
from pyroute2.ipdb import route
from pyroute2.ipdb import interface
from pyroute2.ipdb.transactional import SYNC_TIMEOUT

log = logging.getLogger(__name__)


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
                 ignore_rtables=None, callbacks=None):
        self.mode = mode
        self._event_map = {}
        self._deferred = {}
        self._loaded = set()
        self._mthread = None
        self._nl_own = nl is None
        self._nl_async = config.ipdb_nl_async if nl_async is None else True
        self.mnl = None
        self.nl = nl
        self._plugins = [interface, route, rule]
        if isinstance(ignore_rtables, int):
            self._ignore_rtables = [ignore_rtables, ]
        elif isinstance(ignore_rtables, (list, tuple, set)):
            self._ignore_rtables = ignore_rtables
        else:
            self._ignore_rtables = []
        self._stop = False
        # see also 'register_callback'
        self._post_callbacks = {}
        self._pre_callbacks = {}
        self._cb_threads = {}

        # locks and events
        self.exclusive = threading.RLock()
        self._shutdown_lock = threading.Lock()

        # register callbacks
        #
        # examples::
        #   def cb1(ipdb, msg, event):
        #       print(event, msg)
        #   def cb2(...):
        #       ...
        #
        #   # default mode: post
        #   IPDB(callbacks=[cb1, cb2])
        #   # specify the mode explicitly
        #   IPDB(callbacks=[(cb1, 'pre'), (cb2, 'post')])
        #
        for cba in callbacks or []:
            if not isinstance(cba, (tuple, list, set)):
                cba = (cba, )
            self.register_callback(*cba)

        # load information
        self.restart_on_error = restart_on_error if \
            restart_on_error is not None else nl is None

        # init the database
        self.initdb()

        #
        atexit.register(self.release)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def initdb(self):
        # common event map, empty by default, so all the
        # events aer just ignored
        self.release(complete=False)
        self._stop = False
        # explicitly cleanup object references
        for event in tuple(self._event_map):
            del self._event_map[event]

        # if the command socket is not provided, create it
        if self._nl_own:
            self.nl = IPRoute()
        # setup monitoring socket
        self.mnl = self.nl.clone()
        try:
            self.mnl.bind(async=self._nl_async)
        except:
            self.mnl.close()
            if self._nl_own is None:
                self.nl.close()
            raise

        # explicitly cleanup references
        for key in tuple(self._deferred):
            del self._deferred[key]

        for module in self._plugins:
            for plugin in module.spec:
                self._deferred[plugin['name']] = module.spec
                if plugin['name'] in self._loaded:
                    delattr(self, plugin['name'])
                    self._loaded.remove(plugin['name'])

        # start the monitoring thread
        self._mthread = threading.Thread(name="IPDB event loop",
                                         target=self.serve_forever)
        self._mthread.setDaemon(True)
        self._mthread.start()

    def __getattribute__(self, name):
        deferred = super(IPDB, self).__getattribute__('_deferred')
        if name in deferred:
            register = []
            spec = deferred[name]
            for plugin in spec:
                obj = plugin['class'](self, **plugin['kwarg'])
                setattr(self, plugin['name'], obj)
                register.append(obj)
                self._loaded.add(plugin['name'])
                del deferred[plugin['name']]
            for obj in register:
                if hasattr(obj, '_register'):
                    obj._register()
                if hasattr(obj, '_event_map'):
                    for event in obj._event_map:
                        if event not in self._event_map:
                            self._event_map[event] = []
                        self._event_map[event].append(obj._event_map[event])
        return super(IPDB, self).__getattribute__(name)

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

    def release(self, complete=True):
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
            if self.mnl is not None:
                # terminate the main loop
                for t in range(3):
                    try:
                        msg = ifinfmsg()
                        msg['index'] = 1
                        msg.reset()
                        self.mnl.put(msg, RTM_GETLINK)
                    except Exception as e:
                        logging.warning("shutdown error: %s", e)
                        # Just give up.
                        # We can not handle this case

            if self._mthread is not None:
                self._mthread.join()

            if self.mnl is not None:
                self.mnl.close()
                self.mnl = None
                if complete or self._nl_own:
                    self.nl.close()
                    self.nl = None

        with self.exclusive:
                # collect all the callbacks
                for cuid in tuple(self._cb_threads):
                    for t in tuple(self._cb_threads[cuid]):
                        t.join()

                # flush all the objects
                def flush(idx):
                    for key in tuple(idx.keys()):
                        try:
                            del idx[key]
                        except KeyError:
                            pass
                idx_list = []

                if 'interfaces' in self._loaded:
                    for (key, dev) in self.by_name.items():
                        try:
                            # FIXME
                            self.interfaces._detach(key,
                                                    dev['index'],
                                                    dev.nlmsg)
                        except KeyError:
                            pass
                    idx_list.append(self.ipaddr)
                    idx_list.append(self.neighbours)

                if 'routes' in self._loaded:
                    idx_list.extend([self.routes.tables[x] for x
                                     in self.routes.tables.keys()])

                if 'rules' in self._loaded:
                    idx_list.append(self.rules)

                for idx in idx_list:
                    flush(idx)

    def create(self, kind, ifname, reuse=False, **kwarg):
        return self.interfaces.add(kind, ifname, reuse, **kwarg)

    def commit(self, transactions=None, phase=1):
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
                if phase == 1:
                    s = (target, target.pick(detached=True))
                    snapshots.append(s)
                target.commit(transaction=tx,
                              commit_phase=phase,
                              commit_mask=phase)
        except Exception:
            if phase == 1:
                self.fallen = transactions
                self.commit(transactions=snapshots, phase=2)
            raise
        else:
            if phase == 1:
                for (target, tx) in removed:
                    target['ipdb_scope'] = 'detached'
                    target.detach()
        finally:
            if phase == 1:
                for (target, tx) in transactions:
                    target.drop(tx.uid)

    def watchdog(self, action='RTM_NEWLINK', **kwarg):
        return Watchdog(self, action, kwarg)

    def serve_forever(self):
        ###
        # Main monitoring cycle. It gets messages from the
        # default iproute queue and updates objects in the
        # database.
        #
        # Should not be called manually.
        ###

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
                    if event in self._event_map:
                        for func in self._event_map[event]:
                            func(msg)

                # run post-callbacks
                # NOTE: post-callbacks are asynchronous
                for (cuid, cb) in tuple(self._post_callbacks.items()):
                    t = threading.Thread(name="IPDB callback %s" % (id(cb)),
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
