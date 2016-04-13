.. usage:

Quickstart
==========

Runtime
-------

In the runtime pyroute2 socket objects behave as normal
sockets. One can use them in the poll/select, one can
call `recv()` and `sendmsg()`::

    from pyroute2 import IPRoute

    # create RTNL socket
    ipr = IPRoute()

    # subscribe to broadcast messages
    ipr.bind()

    # wait for data (do not parse it)
    data = ipr.recv(65535)

    # parse received data
    messages = ipr.marshal.parse(data)

    # shortcut: recv() + parse()
    #
    # (under the hood is much more, but for
    # simplicity it's enough to say so)
    #
    messages = ipr.get()


But pyroute2 objects have a lot of methods, written to
handle specific tasks::

    from pyroute2 import IPRoute
    from pyroute2 import IW

    # RTNL interface
    ipr = IPRoute()

    # WIFI interface
    iw = IW()

    # get devices list
    ipr.get_links()

    # scan WIFI networks on wlo1
    iw.scan(ipr.link_lookup(ifname='wlo1'))

More info on specific modules is written in the next
chapters.

Resource release
----------------

Do not forget to release resources and close sockets. Also
keep in mind, that the real fd will be closed only when the
Python GC will collect closed objects.

Signal handlers
---------------

If you place exclusive operations in a signal handler, the
locking will not help. The only way to guard the handler is
to ignore the signal from the handler::

    import signal
    from pyroute2 import IPDB

    def handler(signum, frame):
        # emergency shutdown
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        ipdb.interfaces.test_if.remove().commit()
        ipdb.release()

    def main():
        with IPDB() as ipdb:
            signal.signal(signal.SIGTERM, handler)
            test_if = ipdb.create(ifname='test_if', kind='dummy').commit()
            ...  # do some work

Imports
-------

The public API is exported by `pyroute2/__init__.py`. There
are two main reasons for such approach.

First, it is done so to provide a stable API, that will not
be affected by changes in the package layout. There can be
significant layout changes between versions, but if a
symbol is re-exported via `pyroute2/__init__.py`, it will be
available with the same import signature.

.. warning::
    All other objects are also available for import, but they
    may change signatures in the next versions.

E.g.::

    # Import a pyroute2 class directly. In the next versions
    # the import signature can be changed, e.g., NetNS from
    # pyroute2.netns.nslink it can be moved somewhere else.
    #
    from pyroute2.netns.nslink import NetNS
    ns = NetNS('test')

    # Import the same class from root module. This signature
    # will stay the same, any layout change is reflected in
    # the root module.
    #
    from pyroute2 import NetNS
    ns = NetNS('test')

Another function of `pyroute2/__init__.py` is to provide
deferred imports. Being imported from the root of the
package, classes will be really imported only with the first
constructor call. This make possible to change the base
of pyroute2 classes on the fly.

The proxy class, used in the second case, supports correct
`isinstance()` and `issubclass()` semantics, and in both
cases the code will work in the same way.

There is an exception from the scheme: the exception classes.

Exceptions
----------

Since the deferred import provides wrappers, not real classes,
one can not use them in `try: ... except: ...` statements. So
exception classes are simply reexported here.

Developers note: new exceptions modules **must not** import any
other pyroute2 modules neither directly, nor indirectly. It means
that `__init__.py` files in the import path should not contain
pyroute2 symbols referred in the root module as that would cause
import error due to recursion.

Special cases
=============

eventlet
--------

The eventlet environment conflicts in some way with socket
objects, and pyroute2 provides a workaround for that::

    # import symbols
    #
    import eventlet
    from pyroute2 import NetNS
    from pyroute2.config.eventlet import eventlet_config

    # setup the environment
    eventlet.monkey_patch()
    eventlet_config()

    # run the code
    ns = NetNS('nsname')
    ns.get_routes()
    ...
