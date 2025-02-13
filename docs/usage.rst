.. usage:

.. testsetup:: *

    from pyroute2 import config
    config.mock_netlink = True

Quickstart
==========

"Hello world", sync API:

.. testcode::

    from pyroute2 import IPRoute

    def main():
        ipr = IPRoute()
        for link in ipr.link("dump"):
            print(link.get("ifname"), link.get("state"), link.get("address"))
        ipr.close()

    main()


.. testoutput::

    lo up 00:00:00:00:00:00
    eth0 up 52:54:00:72:58:b2

"Hello world", async API:

.. testcode::

    import asyncio

    from pyroute2 import AsyncIPRoute


    async def main():
        ipr = AsyncIPRoute()
        async for link in await ipr.link("dump"):
            print(link.get("ifname"), link.get("state"), link.get("address"))
        ipr.close()

    asyncio.run(main())


.. testoutput::

    lo up 00:00:00:00:00:00
    eth0 up 52:54:00:72:58:b2

Netlink sockets
---------------

Netlink sockets created with pyroute2 behave similarly to ordinary
socket objects, but there are some key differences in how they
handle data reception.

At a low level, these sockets are monitored by the asyncio event
loop, which means that direct use of `recv()` or `recvmsg()` is not
supported. If you require such low-level functionality, you would
need to modify the protocol class associated with the socket object.

By default, the lowest-level API available for receiving data with
pyroute2 sockets is the `get()` method.

.. testcode::

    from pyroute2 import IPRoute

    # create RTNL socket
    ipr = IPRoute()

    # subscribe to broadcast messages
    ipr.bind()

    # wait for parsed data
    data = ipr.get()


... but pyroute2 objects have additional high level methods:

.. testcode::

    from pyroute2 import IPRoute

    # RTNL interface
    with IPRoute() as ipr:
        # get IP addresses
        for msg in ipr.addr("dump"):
            addr = msg.get("address")
            mask = msg.get("prefixlen")
            print(f"{addr}/{mask}")

.. testoutput::

    127.0.0.1/8
    192.168.122.28/24

Resource release
----------------

Do not forget to release resources and close sockets. Also
keep in mind, that the real fd will be closed only when the
Python GC will collect closed objects.

Imports
-------

The public API is exported by `pyroute2/__init__.py`.

It is done so to provide a stable API that will not be affected
by changes in the package layout. There may be significant
layout changes between versions, but if a symbol is re-exported
via `pyroute2/__init__.py`, it will be available with the same
import signature.

.. warning::
    All other objects are also available for import, but they
    may change signatures in the next versions.

E.g.:

.. testcode::

    # Import a pyroute2 class directly. In the next versions
    # the import signature can be changed, e.g., NetNS from
    # pyroute2.netns.nslink it can be moved somewhere else.
    #
    from pyroute2.iproute.linux import NetNS
    ns = NetNS('test')

    # Import the same class from root module. This signature
    # will stay the same, any layout change is reflected in
    # the root module.
    #
    from pyroute2 import NetNS
    ns = NetNS('test')
