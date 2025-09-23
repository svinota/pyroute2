.. _asyncio:

Library core
============

Intro
-----

Starting from version 0.9.1, pyroute2 is built on an asynchronous core.
This decision was driven not only by long-standing user requests but
also by years of challenges in refactoring the synchronous core.

The complexity lies in the netlink protocol itself. Packets arriving
through the socket can be unordered, and multi-packet responses to
different requests may overlap. In addition, the socket also receives
broadcast netlink packets from the kernel as well as broadcast responses
initiated by other netlink users.

The old core was designed to meet the following requirements:

* The core must be thread-safe.
* No designated management thread; the current reader thread should
  buffer extra packets and pass the buffer to the next reader upon
  exit.
* No implicit background threads; threads should only be started
  upon explicit user request.

While this approach was fast enough, it resulted in a custom event loop
implementation with multiple overlapping locks, making the core code
extremely difficult to maintain.

The current core is built on top of `asyncio`:

* The netlink socket is managed by `asyncio`.
* Raw data reception methods are no longer available to the user.
* All synchronous APIs are now wrappers around the asynchronous API.

As a result, the asynchronous API has become a first-class citizen in
the project, and the code required to reassemble netlink responses has
been reduced by 80%.

AsyncCoreSocket
---------------

.. aafig::
   :scale: 80
   :textual:
   :rounded:

                                                     \
    +------------------+                              |
    | socket           +---+                          |
    +------------------+   |   +-------------------+  |
                           +---+ asyncio transport |  |
    +------------------+   |   +---------+---------+  |
    | asyncio protocol +---+             |            |
    +------------------+       +---------+---------+  |
                               | packets queue     |   \ class AsyncCoreSocket
                               +---------+---------+   /
    +------------------+                 |            |
    | msg reassemble   +<----------------+            |
    +--------+---------+                              |
             |                                        |
             | ... async get()                        |
             |                                        |
             v                                        |
                                                     /

Important `AsyncCoreSocket` components:

* `AsyncCoreSocket.socket` -- thread-local socket-like object managed
  by `.endpoint`
* `AsyncCoreSocket.transport` -- thread-local `asyncio.Transport`
* `AsyncCoreSocket.protocol` -- thread-local `asyncio.Protocol`
* `AsyncCoreSocket.msg_queue` -- thread-local `asyncio` queue for data
  received from the socket
* `AsyncCoreSocket.enqueue()` -- a synchronous routine to enqueue
  packets into `.msg_queue`, used by the `transport` in the `protocol`
* `AsyncCoreSocket.get()` -- an asynchronous routine for retrieving
  packets from the queue and reassembling responses
* `AsyncCoreSocket.marshal` -- a protocol-specific marshal for parsing
  binary data into netlink messages

.. testcode::
    :hide:

    import asyncio
    import inspect

    from pyroute2 import IPRoute
    from pyroute2.netlink.core import CoreMessageQueue
    from pyroute2.netlink.marshal import Marshal

    with IPRoute() as ipr:
        # AsyncCoreSocket.socket, compatibility, management
        assert callable(ipr.asyncore.socket.recv)
        assert callable(ipr.asyncore.socket.send)
        assert callable(ipr.asyncore.socket.recvmsg)
        assert callable(ipr.asyncore.socket.sendmsg)
        assert callable(ipr.asyncore.socket.bind)
        assert ipr.asyncore.transport._sock == ipr.asyncore.socket

        # AsyncCoreSocket.endpoint
        assert isinstance(ipr.asyncore.transport, asyncio.Transport)
        assert isinstance(ipr.asyncore.protocol, asyncio.Protocol)

        # msg_queue
        assert isinstance(ipr.asyncore.msg_queue, CoreMessageQueue)

        # enqueue()
        e_flags = ipr.asyncore.enqueue.__code__.co_flags
        assert callable(ipr.asyncore.enqueue)
        assert not e_flags & inspect.CO_ASYNC_GENERATOR

        # get()
        g_flags = ipr.asyncore.get.__code__.co_flags
        assert callable(ipr.asyncore.get)
        assert g_flags & inspect.CO_ASYNC_GENERATOR

        # marshal
        assert isinstance(ipr.asyncore.marshal, Marshal)


Synchronous code
----------------

`CoreSocket` is the synchronous version of `AsyncCoreSocket` implemented
using wrappers. Since it is merely a wrapper, it also operates on the
`asyncio` event loop.

.. testcode::
    :hide:

    from pyroute2.netlink.core import AsyncCoreSocket, CoreSocket

    with CoreSocket() as cs:
        assert isinstance(cs.asyncore, AsyncCoreSocket)
        assert not isinstance(cs, AsyncCoreSocket)
        assert not issubclass(CoreSocket, AsyncCoreSocket)

`CoreSocket`, as well as other synchronous API classes, uses composition
instead of inheritance. The asynchronous API is available then as
`.asyncore` property.

.. aafig::
   :scale: 80
   :textual:
   :rounded:

                           \
    +------------------+    |
    | AsyncCoreSocket  +    |
    +--------+---------+    |
             |               \ class CoreSocket
             v               /
    +--------+---------+    | 
    | SyncAPI          |    |
    +--------+---------+    |
             |             /
             v


An example of a synchronous wrapper method:

..
    The working directory to build the docs is
    {git_root}/.nox-{user}/{nox_target}/tmp/{docs_sources}
    
    In order to include sources from the git, one should
    step back all the way until {git_root}, thus
    ../../../../

.. literalinclude:: ../../../../pyroute2/netlink/nlsocket.py
   :caption: pyroute2.netlink.nlsocket: class NetlinkSocket
   :pyobject: NetlinkSocket.get
   :linenos:
   :lineno-match:

Synchronous APIs are provided for backward compatibility, and will remain
a part of the library.

All synchronous components are built either on top of `CoreSocket`,
such as `GenericNetlinkSocket`, or using custom wrappers, like in
`IPRoute`. The plan is to refactor all components to provide an asynchronous
API, keeping the synchronous API for compatibility with existing projects
that use pyroute2.
