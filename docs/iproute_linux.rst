.. _iproute_linux:

.. testsetup:: *

   from pyroute2 import config, IPRoute
   config.mock_netlink = True
   ipr = IPRoute()

.. testcleanup:: *

   ipr.close()


Linux systems
-------------

.. automodule:: pyroute2.iproute.linux

.. autoclass:: pyroute2.iproute.linux.RTNL_API
   :members:
