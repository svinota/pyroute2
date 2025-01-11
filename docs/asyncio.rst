.. _asyncio:

.. testsetup:: *

    from pyroute2 import config
    config.mock_iproute = True

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

* `AsyncCoreSocket.socket` -- thread-local `socket.socket` object,
  managed by `.endpoint`
* `AsyncCoreSocket.endpoint` -- thread-local `asyncio` endpoint
  `(transport, protocol)`
* `AsyncCoreSocket.msg_queue` -- thread-local `asyncio` queue for data
  received from the socket
* `AsyncCoreSocket.enqueue()` -- a synchronous routine to enqueue
  packets into `.msg_queue`, used by the `transport` in the `protocol`
* `AsyncCoreSocket.get()` -- an asynchronous routine for retrieving
  packets from the queue and reassembling responses
* `AsyncCoreSocket.marshal` -- a protocol-specific marshal for parsing
  binary data into netlink messages

Synchronous code
----------------

`CoreSocket` is the synchronous version of `AsyncCoreSocket` implemented
using wrappers. Since it is merely a wrapper, it also operates on the
`asyncio` event loop.

`CoreSocket`, as well as other synchronous API classes, uses composition
instead of inheritance. The asynchronous API is available then as
`.asyncore` property.

.. aafig::
   :scale: 80
   :textual:

                           \
    +------------------+    |
    | AsyncCoreSocket  +    |
    +--------+---------+     \ class CoreSocket
             |               /
    +--------+---------+    | 
    | SyncAPI wrappers |    |
    +------------------+    |
                           /


An example of a synchronous wrapper method:

.. literalinclude:: ../../../../pyroute2/netlink/core.py
   :caption: pyroute2.netlink.core: class SyncAPI
   :pyobject: SyncAPI.get
   :linenos:
   :lineno-match:

Synchronous APIs are provided for backward compatibility, and will remain
a part of the library.

All synchronous components are built either on top of `CoreSocket`,
such as `GenericNetlinkSocket`, or using custom wrappers, like in
`IPRoute`. The plan is to refactor all components to provide an asynchronous
API, keeping the synchronous API for compatibility with existing projects
that use pyroute2.

Thread safety
-------------

Is the current core thread-safe? Yes and no at the same time. While there
are no locks in the core, components like sockets and message queues are 
now thread-local.

This means that the same pyroute2 socket object manages as many
underlying netlink sockets as there are threads accessing it.

Pros:

* Simplicity and absence of mutexes, which eliminates the risk of deadlocks.

Cons:

* Race conditions are still possible if shared data is not thread-local.
* Debugging existing netlink flows at runtime is limited because any
  debugger session will create its own underlying netlink socket. This
  makes logging and post-mortem analysis more important.
