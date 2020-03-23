.. _remote:

RemoteIPRoute
-------------

Caveats
=======

.. warning::
   The class implies a serious performance penalty. Please consider
   other options if you expect high loads of the netlink traffic.

.. warning::
   The class requires the mitogen library that should be installed
   separately: https://mitogen.readthedocs.io/en/latest/

.. warning::
   The object of this class implicitly spawn child processes. Beware.

Here are some reasons why this class is not used as a general class instead
of specific IPRoute for local RTNL, and NetNS for local netns management:

* The performance of the Python parser for the binary netlink protocol
  is not so good, but using such proxies makes it even worse.
* Local IPRoute and NetNS access is the core functionality and must
  work with no additional libraries installed.

Introduction
============

It is possible to run IPRoute instances remotely using the mitogen
library. The remote node must have same python version installed,
but no additional libraries are required there: all the code will
be imported from the host where you start your script.

The simplest case, run IPRoute on a remote Linux host via ssh
(assume the keys are deployed)::

   from pyroute2 import RemoteIPRoute

   rip = RemoteIPRoute(protocol='ssh',
                       hostname='test01',
                       username='ci')
   rip.get_links()

   # ...

Indirect access
===============

Building mitogen proxy chains you can access nodes indirectly::

   import mitogen.master
   from pyroute2 import RemoteIPRoute

   broker = mitogen.master.Broker()
   router = mitogen.master.Router(broker)
   # login to the gateway
   gw = router.ssh(hostname='test-gateway',
                   username='ci')
   # login from the gateway to the target node
   host = router.ssh(via=gw,
                     hostname='test01',
                     username='ci')

   rip = RemoteIPRoute(router=router, context=host)

   rip.get_links()

   # ...

Run with privileges
===================

It requires the mitogen sudo proxy to run IPRoute with root permissions::

   import mitogen.master
   from pyroute2 import RemoteIPRoute

   broker = mitogen.master.Broker()
   router = mitogen.master.Router(broker)
   host = router.ssh(hostname='test01', username='ci')
   sudo = router.sudo(via=host, username='root')

   rip = RemoteIPRoute(router=router, context=sudo)

   rip.link('add', ifname='br0', kind='bridge')

   # ...


Remote network namespaces
=========================

You also can access remote network namespaces with the same RemoteIPRoute
object::

   import mitogen.master
   from pyroute2 import RemoteIPRoute

   broker = mitogen.master.Broker()
   router = mitogen.master.Router(broker)
   host = router.ssh(hostname='test01', username='ci')
   sudo = router.sudo(via=host, username='root')

   rip = RemoteIPRoute(router=router, context=sudo, netns='test-netns')

   rip.link('add', ifname='br0', kind='bridge')

   # ...
