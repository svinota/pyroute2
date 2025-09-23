.. _iproute_netns:


.. testsetup:: *

    from pyroute2 import config
    config.mock_netlink = True

Using namespaces
----------------

The code to init a netlink socket in a network namespace was
moved to the library core. To run a socket within a netns, simply
pass `netns` argument to the socket init:

.. testcode:: netns00

    import asyncio

    from pyroute2 import AsyncIPRoute


    async def main():
        async with AsyncIPRoute(netns="test") as ipr:
            print(f"current netns: {ipr.status['netns']}")

    asyncio.run(main())

.. testoutput:: netns00

    current netns: test

It is possible to use the old `NetNS` class, it is now just a compatibility
wrapper for the new API:

.. testcode:: netns01

    from pyroute2 import NetNS

    with NetNS("test") as ns:
        print(f"current netns: {ns.status['netns']}")

.. testoutput:: netns01

    current netns: test

Flags also might be used with any constructor. The default flags are
`os.O_CREAT`, which means that the network namespace will be created
if doesn't exist. Using 0 as `flags` value means that the constructor
will fail, if the network namespace doesn't exist already:

.. testcode:: netns02

    from pyroute2 import IPRoute

    try:
        ipr = IPRoute(netns="foo", flags=0)
    except FileNotFoundError:
        print("netns doesn't exist, refuse to start")

.. testoutput:: netns02

    netns doesn't exist, refuse to start

The init routine works now as follows:

* fork a child using `pyroute2.config.child_process_mode`, which can be
  either `"fork"` (default) for `os.fork()` or `"mp"` for
  `multiprocessing.Process()` (safer and slower).
* start a socket in the child
* send the socket FD back to the parent
* init a socket in the parent using the FD from the child
* exit the child

.. testcode:: netns-config
   :hide:

   from pyroute2 import config
   assert isinstance(config.child_process_mode, str)

An important note about `pyroute2.config.child_process_mode`: while the
`"fork"` mode might be significantly faster than `"mp"` on some setups
and versions, it is not threadsafe, and you will get warnings from Python
when using it in multithreaded applications. The socket init routine is
written to be safe even under these circumstances, but ye warned.
