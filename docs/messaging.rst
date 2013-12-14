.. messaging:

pyroute2 as a messaging system
==============================

It is possible to use pyroute2 library as a messaging system.
Initially it was written to provide a remote netlink access, but
occasionally it evolved into a simple messaging system, that
supports REP/REQ, PUSH/PULL and SUBSCRIBE models. Supported
transports are:

* raw TCP: `tcp://host:port`
* SSLv3: `ssl://host:port`
* TLSv1: `tls://host:port`
* UDP: `udp://host:port` -- only for PUSH/PULL
* raw UNIX sockets: `unix://path`
* UNIX + SSLv3: `unix+ssl://path`
* UNIX + TLSv1: `unix+tls://path`
 
.. note::
    On Linux, it is possible to use the abstract socket namespace.
    To create such connection, use `unix://\\x00path` notation.

.. note::
    It is possible to use both absolute and relative paths for
    UNIX sockets: `unix:///an/absolute/path` and
    `unix://a/relative/path`

.. note::
    UDP sockets can be used only for PUSH/PULL model.

Unlike other messaging systems, it is totally up to developer,
which model to use: there is no socket types.

All examples will be done with IPRoute class, but all the some
is true for all Netlink-based classes.

REP/REQ model
-------------

Server::

    from pyroute2 import IPRoute

    ipr = IPRoute()
    ipr.serve('tcp://localhost:9824')
    ...  # wait for some event to exit
    ipr.release()

Client::

    from pyroute2 import IPRoute

    ipr = IPRoute(host='tcp://localhost:9824')
    print(ipr.get_addr())
    ipr.release()

PUSH/PULL model
---------------

Server gets events from client and print them::

    from pyroute2 import IPRoute

    ipr = IPRoute(do_connect=False)
    ipr.serve('udp://localhost:9824')
    ipr.monitor()

    while True:
        msg = ipr.get(raw=True)  # raw=True -- don't wait NLMSG_DONE
        print(msg)

    ip.release()

Client pushes messages::

    from pyroute2 import IPRoute

    ipr = IPRoute()
    addr = ipr.connect('udp://localhost:9824')

    for msg in ipr.get_addr():
        ipr.nlm_push(msg, realm=addr)

    ipr.disconnect(addr)
    ipr.release()

SUBSCRIBE
---------

Server provides events from OS level::

    from pyroute2 import IPRoute

    ipr = IPRoute()
    ipr.serve('ssl://localhost:9824',
              key='server.key',
              cert='server.crt',
              ca='ca.crt')
    ...  # wait for some event to exit
    ipr.release()

Client monitors events::

    from pyroute2 import IPRoute

    ipr = IPRoute(host='ssl://localhost:9824',
                  key='client.key',
                  cert='client.crt',
                  ca='ca.crt')
    while True:
        msg = ipr.get()
        print(msg)

    ipr.release()
