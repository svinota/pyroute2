.. usage:

.. testsetup:: *

    from pyroute2 import config
    config.mock_iproute = True

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
        await ipr.close()

    asyncio.run(main())


.. testoutput::

    lo up 00:00:00:00:00:00
    eth0 up 52:54:00:72:58:b2

Sockets
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

    # RTNL interface
    with IPRoute() as ipr:

        # get devices list
        ipr.get_links()

        # get addresses
        ipr.get_addr()

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

Special cases
=============

eventlet
--------

The eventlet environment conflicts in some way with socket
objects, and pyroute2 provides some workaround for that::

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

This may help, but not always. In general, the pyroute2 library
is not eventlet-friendly.
