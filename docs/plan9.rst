.. _plan9:

.. testsetup::

    import asyncio

    from pyroute2.plan9.server import Plan9ServerSocket
    from pyroute2.plan9.client import Plan9ClientSocket


Plan9 9p2000 protocol
=====================

The library provides basic asynchronous 9p2000 implementation.

.. autoclass:: pyroute2.plan9.server.Plan9ServerSocket
    :members:

.. autoclass:: pyroute2.plan9.client.Plan9ClientSocket
    :members:
