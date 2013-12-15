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

Building blocks
---------------

General scheme::

    API (client) <--> Broker <--> Broker <-...
                        ^
                        |
                        v
                  Target service

Brokers:

* Route packets
* Buffer packets and manage channels bandwidth
* Tag/untag packets
* Manage connections with other brokers and services
* Provide management API

Clients:

* Encode/decode packets to/from services
* Tag/untag packets into/from the transport protocol
* Manage connected brokers via management API

Services:

* Get untagged packets from clients via brokers
* Issue responses
* Issue broadcasts

Transport protocol
^^^^^^^^^^^^^^^^^^

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
        uint32 dst;  /* target subsystem addr */
        uint32 src;  /* not used yet */
    };

    struct nla_hdr {
        uint16 length;
        uint16 type;  /* == 0; now it is the only NLA for envmsg */
    };

.. warning:
    Message format is not final yet and will become a standard after
    discussions.

Then follows binary data of incapsulated messages. Length type of
uint16 limits data to 65535 bytes. Fragmentation and reassembling
of larger messages is up to client and service; brokers have nothing
to do with message reassembling.

Control protocol
^^^^^^^^^^^^^^^^

Control messages go between clients and brokers incapsulated in the
transport messages; `flags` field of nlhdr should be set to 1.

Control message format::

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

    array of NLAs

