'''
..
    8<-----------------------------------------------------------
    Doctest setup.

    It is not rendered into html. For the docs, skip to tne
    CI test fixtures section below.

.. testsetup:: *

    from pyroute2.fixtures.doctest import *

..
    End of the doctest setup.
    8<-----------------------------------------------------------


CI test fixtures
----------------

The library provides a set of fixtures that can be used with pytest
to setup a simple test environment for functional network tests.

The fixtures set up a network namespace with a unique name, a dummy
interface within the namespace, and bring the interface up. They form
a tree of dependencies, so if you use e.g. `test_link_ifname` fixture,
you may be sure that the namespace and the interface are already set
up properly.

Fixtures dependencies diagram:

.. aafig::
    :scale: 80
    :textual:

                        +---------------------+
                        | `test_link`         |--+
                        +---------------------+  |
                             ^           |       v
    +---------------------+  |           |  +----------------------+
    | `test_link_index`   |__+           |  | `test_link_ifinfmsg` |
    +---------------------+  |           |  +----------------------+
                             |           |       |
    +---------------------+  |           |       v
    | `test_link_address` |__+           |  +----------------------+
    +---------------------+  |           +->| netns                |
                             |           |  +----------------------+
    +---------------------+  |           |
    | `test_link_ifname`  |__+           |
    +---------------------+  |           |
                             |           |
    +---------------------+  |           |
    | `async_context`     |__+           |
    |                     |_ | ___       |
    +---------------------+  |    |      |
                             |    |      |
    +---------------------+  |    |      |
    | `sync_context`      |__|    |      |
    |                     |_____  |      |
    +---------------------+     | |      |
                                | |      |
    +---------------------+     | |      |
    | `sync_ipr`          |<----+ |      |
    |                     |______ | _____+
    +---------------------+       |      |
                                  |      |
    +---------------------+       |      |
    | `async_ipr`         |<------+      |
    |                     |______________+
    +---------------------+              |
                                         |
    +---------------------+              |
    | `ndb`               |______________|
    +---------------------+

.. autofunction:: pyroute2.fixtures.iproute._nsname

.. autofunction:: pyroute2.fixtures.iproute._test_link_ifinfmsg

.. autofunction:: pyroute2.fixtures.iproute._test_link

.. autofunction:: pyroute2.fixtures.iproute._test_link_address

.. autofunction:: pyroute2.fixtures.iproute._test_link_index

.. autofunction:: pyroute2.fixtures.iproute._test_link_ifname

.. autofunction:: pyroute2.fixtures.iproute._async_ipr

.. autofunction:: pyroute2.fixtures.iproute._sync_ipr

.. autofunction:: pyroute2.fixtures.iproute._async_context

.. autofunction:: pyroute2.fixtures.iproute._sync_context

.. autofunction:: pyroute2.fixtures.iproute._ndb

.. autoclass:: pyroute2.fixtures.iproute.TestInterface
    :members:

.. autoclass:: pyroute2.fixtures.iproute.TestContext
    :members:

'''
