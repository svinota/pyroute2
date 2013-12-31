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
    from pprint import pprint

    ipr = IPRoute(host='tcp://localhost:9824')
    pprint(ipr.get_addr())
    ipr.release()

PUSH/PULL model
---------------

Server gets event from client and prints it::

    from pyroute2 import IOCore

    ioc = IOCore()
    ioc.serve('tcp://localhost:9824')
    ioc.provide('push')  # just arbitrary string ID of the service
    ioc.monitor()

    msg = ioc.get()
    print(msg)

    ioc.release()

Client pushes arbitrary data as a string::

    from pyroute2 import IOCore

    ipr = IOCore()
    (uid, addr) = ioc.connect('tcp://localhost:9824')
    port = ioc.discover('push', addr)  # service ID from ioc.provide()

    ioc.push((addr, port), 'hello, world!')

    ipr.release()


Building blocks
---------------

General scheme::

    Service code
     ^
     |
     | (1)
     |
     v
    IOCore   IOCore
     ^        ^
     |        |
     | (2)    |
     |        |
     v        v
      IOBroker  <-- (3) --> Linux kernel
          ^
          |
          | (4)
          |
          v
      IOBroker  ...


Protocols:

1. API calls
2. Transport netlink
3. Netlink
4. Transport netlink

.. note::
    Netlink gate is integrated into IOBroker by historical reason:
    pyroute2 was started as a one-host netlink library. Later this
    code will be isolated as a service.

IOBrokers:

* Route packets
* Buffer packets and manage channels bandwidth
* Tag/untag packets
* Manage connections with other brokers and services
* Provide management API

IOCores:

* Encode/decode packets to/from services
* Tag/untag packets into/from the transport protocol
* Manage connected brokers via management API

Services:

* Get untagged packets from clients via brokers
* Issue responses
* Issue requests to other services

Transport netlink
^^^^^^^^^^^^^^^^^

All the packets between clients and brokers should be incapsulated
into the transport protocol messages. Each transport message consists of::

    struct nlhdr {
        uint32 length;
        uint16 type;
        uint16 flags;
        uint32 sequence_number;
        uint32 pid;
    };

    struct envmsghdr {
        uint32 dst;    /* destination node */
        uint32 dport;  /* destination service */
        uint32 src;    /* source node */
        uint32 sport;  /* source service */
        uint16 ttl;    /* ttl, decreased on each hop */
        uint16 reserved;
    };

    struct nla_hdr {
        uint16 length;
        uint16 type;  /* == 0; now it is the only NLA for envmsg */
    };

.. warning:
    Message format is not final yet and will become stable after
    discussions.

Then follows binary data of incapsulated messages. Length type of
uint16 limits data to 65535 bytes. Fragmentation and reassembling
of larger messages is up to client and service; brokers have nothing
to do with message reassembling.

Control protocol
^^^^^^^^^^^^^^^^

Control messages go between clients and brokers incapsulated in the
transport messages; `flags` field of nlhdr should be set to 1 (request)
or 3 (response)

Control message format is the same as for generic netlink packets::

    struct nlhdr {
        uint32 length;
        uint16 type;
        uint16 flags;
        uint32 sequence_number;
        uint32 pid;
    };

    struct genlmsghdr {
        uint8 cmd;
        uint8 version;
        uint16 reserved;
    }

    [ array of NLA ]

