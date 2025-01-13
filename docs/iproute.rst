.. _iproute:

IPRoute module
==============

.. toctree::
    :maxdepth: 2

    iproute_intro
    iproute_netns

..
    iproute_platforms
    iproute_reference
    iproute_tc


BSD systems
-----------

.. automodule:: pyroute2.iproute.bsd

Windows systems
---------------

.. automodule:: pyroute2.iproute.windows

.. autoclass:: pyroute2.iproute.windows.IPRoute
    :members:

Linux systems
-------------

.. automodule:: pyroute2.iproute.linux
    :members:

Queueing disciplines
--------------------

.. automodule:: pyroute2.netlink.rtnl.tcmsg.sched_drr
    :members:

.. automodule:: pyroute2.netlink.rtnl.tcmsg.sched_choke
    :members:

.. automodule:: pyroute2.netlink.rtnl.tcmsg.sched_clsact
    :members:

.. automodule:: pyroute2.netlink.rtnl.tcmsg.sched_hfsc
    :members:

.. automodule:: pyroute2.netlink.rtnl.tcmsg.sched_htb
    :members:

Filters
-------

.. automodule:: pyroute2.netlink.rtnl.tcmsg.cls_u32
