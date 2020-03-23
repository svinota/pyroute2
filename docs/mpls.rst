.. mpls:

MPLS howto
----------

Short introduction into Linux MPLS. Requirements:

* kernel >= 4.4
* modules: `mpls_router`, `mpls_iptunnel`
* `$ sudo sysctl net.mpls.platform_labels=$x`, where `$x` -- number of labels
* `pyroute2` >= 0.4.0

MPLS labels
===========

Possible label formats::

    # int
    "newdst": 20

    # list of ints
    "newdst": [20]
    "newdst": [20, 30]

    # string
    "newdst": "20/30"

    # dict
    "newdst": {"label": 20}

    # list of dicts
    "newdst": [{"label": 20, "tc": 0, "bos": 0, "ttl": 16},
               {"label": 30, "tc": 0, "bos": 1, "ttl": 16}]


IPRoute
=======

MPLS routes
~~~~~~~~~~~

Label swap::

    from pyroute2 import IPRoute
    from pyroute2.common import AF_MPLS

    ipr = IPRoute()
    # get the `eth0` interface's index:
    idx = ipr.link_lookup(ifname="eth0")[0]
    # create the request
    req = {"family": AF_MPLS,
           "oif": idx,
           "dst": 20,
           "newdst": [30]}
    # set up the route
    ipr.route("add", **req)

Please notice that "dst" can specify only one label, even being a list.
Label push::

    req = {"family": AF_MPLS,
           "oif": idx,
           "dst": 20,
           "newdst": [20, 30]}
    ipr.route("add", **req)

One can set up also the `via` field::

    from socket import AF_INET

    req = {"family": AF_MPLS,
           "oif": idx,
           "dst": 20,
           "newdst": [30],
           "via": {"family": AF_INET,
                   "addr": "1.2.3.4"}}
    ipr.route("add", **req)

MPLS lwtunnel
~~~~~~~~~~~~~

To inject IP packets into MPLS::

    req = {"dst": "1.2.3.0/24",
           "oif": idx,
           "encap": {"type": "mpls",
                     "labels": [202, 303]}}
    ipr.route("add", **req)

NDB
===

.. note:: basic MPLS routes management in NDB since version 0.5.11

List MPLS routes::

    >>> from pyroute2.common import AF_MPLS
    >>> ndb.routes.dump().filter(family=AF_MPLS)
    ('localhost', 0, 28, 20, 0, 0, 254, 4, 0, 1, 0, ...
    ('localhost', 0, 28, 20, 0, 0, 254, 4, 0, 1, 0, ...

    >>> ndb.routes.dump().filter(family=AF_MPLS).select('oif', 'dst', 'newdst')
    (40627, '[{"label": 16, "tc": 0, "bos": 1, "ttl": 0}]', '[{"label": 500, ...
    (40627, '[{"label": 40, "tc": 0, "bos": 1, "ttl": 0}]', '[{"label": 40, ...

List lwtunnel routes::

    >>> ndb.routes.dump().filter(lambda x: x.encap is not None)
    ('localhost', 0, 2, 24, 0, 0, 254, 4, 0, 1, 16, '10.255.145.0', ...
    ('localhost', 0, 2, 24, 0, 0, 254, 4, 0, 1, 0, '192.168.142.0', ...

    >>> ndb.routes.dump().filter(lambda x: x.encap is not None).select('dst', 'encap') 
    ('10.255.145.0', '[{"label": 20, "tc": 0, "bos": 0, "ttl": 0}, ...
    ('192.168.142.0', '[{"label": 20, "tc": 0, "bos": 0, "ttl": 0}, ...

Create MPLS routes::

    >>> from pyroute2.common import AF_MPLS
    >>> ndb.routes.create(family=AF_MPLS,
                          dst=128,                       # label
                          oif=1,                         # output interface
                          newdst=[128, 132]).commit()    # label stack

Create lwtunnel::

    >>> ndb.routes.create(dst='192.168.145.0/24',
                          gateway='192.168.140.5', 
                          encap={'type': 'mpls',
                                 'labels': [128, 132]}).commit()

