'''
Developer's guide to Netlink and pyroute2

Generic netlink protocol
========================

General netlink packet structure::

    nlmsg packet:
        + header
        + data

Generic netlink message header::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid

The `length` field is the length of all the packet, including
data and header. The `type` field is used to distinguish different
message types, commands etc. Please note, that there is no
explicit protocol field -- you choose a netlink protocol, when
you create a socket.

The `sequence number` is very important. Netlink is an asynchronous
protocol -- it means, that the packet order doesn't matter. But
responses to a request are always marked with the same sequence
number, so you can treat it as a cookie.

Please keep in mind, that a netlink request can initiate a
cascade of events, and netlink messages from these events can
carry sequence number == 0. E.g., it is so when you remove a
primary IP addr from an interface, when `promote_secondaries`
sysctl is set.

Beside of incapsulated headers and other protocol-specific data,
netlink messages can carry NLA (netlink attributes). NLA
structure is as follows::

    NLA header:
        + uint16 length
        + uint16 type
    NLA data:
        + data-specific struct
        # optional:
        + NLA
        + NLA
        + ...

So, NLA structures can be nested, forming a tree.

Complete structure of a netlink packet::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid
    [ optional protocol-specific data ]
    [ optional NLA tree ]

More information about netlink protocol you can find in
the man pages.

Protocol sample: RTNL
=====================

RTNL is a netlink protocol, used to get and set information
about different network objects -- addresses, routes, interfaces
etc.

RTNL protocol-specific data in messages depends on the object
type. E.g., complete packet with the interface address information::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid
    ifaddrmsg structure:
        + unsigned char ifa_family
        + unsigned char ifa_prefixlen
        + unsigned char ifa_flags
        + unsigned char ifa_scope
        + uint32 ifa_index
    [ optional NLA tree ]

NLA for this kind of packets can be of type IFA_ADDRESS, IFA_LOCAL
etc. -- please refer to the corresponding source.

Other objects types require different structures, sometimes really
complex. All these structures are described in sources.

Pyroute2 netlink description syntax
===================================

To simplify the development, pyroute2 provides an easy way to
describe packet structure. As an example, you can take the
ifaddrmsg description -- `pyroute2/netlink/rtnl/ifaddrmsg.py`.

To describe a packet, you need to inherit from `nlmsg` class::

    from pyroute2.netlink.generic import nlmsg

    class foo_msg(nlmsg):
        fields = ( ... )
        nla_map = ( ... )

NLA are described in the same way, but the parent class should be
`nla`, instead of `nlmsg`. And yes, it is important to use the
proper parent class.

fields attribute
++++++++++++++++

The `fields` attribute describes the structure of the
protocol-specific data. It is a tuple of tuples, where each
member contains a field name and its data format.

Field data format should be specified as for Python `struct`
module. E.g., ifaddrmsg structure::

    ifaddrmsg structure:
        + unsigned char ifa_family
        + unsigned char ifa_prefixlen
        + unsigned char ifa_flags
        + unsigned char ifa_scope
        + int ifa_index

should be described as follows::

    class ifaddrmsg(nlmsg):
        fields = (('family', 'B'),
                  ('prefixlen', 'B'),
                  ('flags', 'B'),
                  ('scope', 'B'),
                  ('index', 'I'))

Format strings are passed directly to the `struct` module,
so you can use all the notations like `>I`, `16s` etc. All
fields are parsed from the stream separately, so if you
want to explicitly fix alignemt, as if it were C struct,
use the `pack` attribute::

    class tstats(nla):
        pack = "struct"
        fields = (('version', 'H'),
                  ('ac_exitcode', 'I'),
                  ('ac_flag', 'B'),
                  ...)

nla_map attribute
+++++++++++++++++

The `nla_map` attribute is a tuple of NLA descriptions. Each
description is also a tuple in two different forms: either
two fields, name and format, or three fields: type, name and
format.

Please notice, that the format field is a string name of
corresponding NLA class::

    class ifaddrmsg(nlmsg):
        ...
        nla_map = (('IFA_UNSPEC',  'hex'),
                   ('IFA_ADDRESS', 'ipaddr'),
                   ('IFA_LOCAL', 'ipaddr'),
                   ...)

This code will create mapping, where IFA_ADDRESS NLA will be of
type 1 and IFA_LOCAL -- of type 2, etc. Both NLA will be decoded
as IP addresses (class `ipaddr`). IFA_UNSPEC will be of type 0,
and if it will be in the NLA tree, it will be just dumped in hex.

NLA class names are should be specified as strings, since they
are resolved in runtime.

There are several pre-defined NLA types, that you will get with
`nla` class:

* none  # forces pyroute2 just to skip this NLA
* uint8
* uint16
* uint32  # there are dedicated NLA of these types as well
* ipaddr  # IP address, IPv4 or IPv6, depending on the socket
* l2addr  # MAC address
* hex     # hex dump as a string -- useful for debugging
* cdata   # just a binary string
* asciiz  # zero-terminated ASCII string

Please refer to `pyroute2/netlink/generic.py` for details.

You can also make your own NLA descriptions::

    class ifaddrmsg(nlmsg):
        ...
        nla_map = (...
                   ('IFA_CACHEINFO', 'cacheinfo'),
                   ...)

        class cacheinfo(nla):
            fields = (('ifa_prefered', 'I'),
                      ('ifa_valid', 'I'),
                      ('cstamp', 'I'),
                      ('tstamp', 'I'))

Custom NLA descriptions should be defined in the same class,
where they are used.

Also, it is possible to use not autogenerated type numbers, as
for ifaddrmsg, but specify them explicitly::

    class iw_event(nla):
        ...
        nla_map = ((0x8B00, 'SIOCSIWCOMMIT', 'hex'),
                   (0x8B01, 'SIOCGIWNAME', 'hex'),
                   (0x8B02, 'SIOCSIWNWID', 'hex'),
                   (0x8B03, 'SIOCGIWNWID', 'hex'),
                   ...)

Here you can see custom NLA type numbers -- 0x8B00, 0x8B01 etc.
It is not permitted to mix these two forms in one class: you should
use ether autogenerated type numbers (two fields tuples), or
explicit numbers (three fields typles).

Parsed netlink message
======================

Netlink messages are represented by pyroute2 as dictionaries
as follows::

    {'header': {'pid': ...,
                'length: ...,
                'flags': ...,
                'error': None,  # if you are lucky
                'type': ...,
                'sequence_number': ...},

     # fields attributes
     'field_name1': value,
     ...
     'field_nameX': value,

     # nla tree
     'attrs': [['NLA_NAME1', value],
               ...
               ['NLA_NAMEX', value],
               ['NLA_NAMEY', {'field_name1': value,
                              ...
                              'field_nameX': value,
                              'attrs': [['NLA_NAME.... ]]}]]}

As an example, a message from the wireless subsystem about new
scan event::

    {'index': 4,
     'family': 0,
     '__align': 0,
     'header': {'pid': 0,
                'length': 64,
                'flags': 0,
                'error': None,
                'type': 16,
                'sequence_number': 0},
     'flags': 69699,
     'ifi_type': 1,
     'event': 'RTM_NEWLINK',
     'change': 0,
     'attrs': [['IFLA_IFNAME', 'wlp3s0'],
               ['IFLA_WIRELESS',
                {'attrs': [['SIOCGIWSCAN',
                            '00:00:00:00:00:00:00:00:00:00:00:00']]}]]}

Create and send a message
=========================

Using high-level interfaces like `IPRoute` or `IPDB`, you will never
need to manually construct and send netlink messages. But in the case
you really need it, it is simple as well.

Having a description class, like `ifaddrmsg` from above, you need to:

* instantiate it
* fill the fields
* encode the packet
* send the encoded data

The code::

    from pyroute2.netlink import NLM_F_REQUEST
    from pyroute2.netlink import NLM_F_ACK
    from pyroute2.netlink import NLM_F_CREATE
    from pyroute2.netlink import NLM_F_EXCL
    from pyroute2.netlink.iproute import RTM_NEWADDR
    from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

    ##
    # add an addr to an interface
    #

    # create the message
    msg = ifaddrmsg()

    # fill the protocol-specific fields
    msg['index'] = index  # index of the interface
    msg['family'] = AF_INET  # address family
    msg['prefixlen'] = 24  # the address mask
    msg['scope'] = scope  # see /etc/iproute2/rt_scopes

    # attach NLA -- it MUST be a list / mutable
    msg['attrs'] = [['IFA_LOCAL', '192.168.0.1'],
                    ['IFA_ADDRESS', '192.162.0.1']]

    # fill generic netlink fields
    msg['header']['sequence_number'] = nonce  # an unique seq number
    msg['header']['pid'] = os.getpid()
    msg['header']['type'] = RTM_NEWADDR
    msg['header']['flags'] = NLM_F_REQUEST |\\
                             NLM_F_ACK |\\
                             NLM_F_CREATE |\\
                             NLM_F_EXCL

    # encode the packet
    msg.encode()

    # send the buffer
    nlsock.send(msg.buf.getvalue())

Please notice, that NLA list *MUST* be mutable.
'''
