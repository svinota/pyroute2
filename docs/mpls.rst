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
    "dst": 20

    # list of ints
    "newdst": [20]
    "newdst": [20, 30]

    # string
    "labels": "20/30"

Any of these notations should be accepted by `pyroute2`, if not -- try
another format and submit an issue to the project github page. The code
is quite new, some issues are possible.

Refer also to the test cases, there are many usage samples:

* `tests/general/test_ipr.py`
* `tests/general/test_ipdb.py`

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

Notice, that `dst` is a single label, while `newdst` is a stack. Label push::

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

IPDB
====

MPLS routes
~~~~~~~~~~~

The `IPDB` database also supports MPLS routes, they are reflected in the
`ipdb.routes.tables["mpls"]`::

    >>> (ipdb
    ...  .routes
    ...  .add({"family": AF_MPLS,
    ...        "oif": ipdb.interfaces["eth0"]["index"],
    ...        "dst": 20,
    ...        "newdst": [30]})
    ...  .commit())
    <skip>
    >>> (ipdb
    ...  .routes
    ...  .add({"family": AF_MPLS,
    ...        "oif": ipdb.interfaces["eth0"]["index"],
    ...        "dst": 22,
    ...        "newdst": [22, 42]})
    ...  .commit())
    <skip>
    >>> ipdb.routes.tables["mpls"].keys()
    [20, 22]

Pls notice, that there is only one MPLS routing table.

Multipath MPLS::

    with IDPB() as ipdb:
        (ipdb
         .routes
         .add({"family": AF_MPLS,
               "dst": 20,
               "multipath": [{"via": {"family": AF_INET,
                                      "addr": "10.0.0.2"},
                              "oif": ipdb.interfaces["eth0"]["index"],
                              "newdst": [30]},
                             {"via": {"family": AF_INET,
                                      "addr": "10.0.0.3"},
                              "oif": ipdb.interfaces["eth0"]["index"],
                              "newdst": [40]}]})
         .commit())

MPLS lwtunnel
~~~~~~~~~~~~~

LWtunnel routes reside in common route tables::

    with IPDB() as ipdb:
        (ipdb
         .routes
         .add({"dst": "1.2.3.0/24",
               "oif": ipdb.interfaces["eth0"]["index"],
               "encap": {"type": "mpls",
                         "labels": [22]}})
         .commit())
        print(ipdb.routes["1.2.3.0/24"])

Multipath MPLS lwtunnel::

    with IPDB() as ipdb:
        (ipdb
         .routes
         .add({"dst": "1.2.3.0/24",
               "table": 200,
               "multipath": [{"oif": ipdb.interfaces["eth0"]["index"],
                              "gateway": "10.0.0.2",
                              "encap": {"type": "mpls",
                                        "labels": [200, 300]}},
                             {"oif": ipdb.interfaces["eth1"]["index"],
                              "gateway": "172.16.0.2",
                              "encap": {"type": "mpls",
                                        "labels": [200, 300]}}]})
         .commit())
        print(ipdb.routes.tables[200]["1.2.3.0/24"])
