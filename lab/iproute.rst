IPRoute -- work with interfaces, addresses and routes
-----------------------------------------------------

.. _dmesg:

The lab requires JavaScript to be enabled, as it runs Python over JS. It
may be also incompatible with your browser, so consider using FireFox,
Chrome or like that.


Create IPRoute and get network objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`IPRoute` objects provide kernel RTNL API, just as Linux `iproute2` utility
does. The differences are that `IPRoute` provides a subset -- so your
contributions are more than welcome, -- and `IPRoute` returns parsed
netlink packets, only adding a few extra fields.

.. note::
    Netlink protocol and packets structure: https://docs.pyroute2.org/netlink.html

    More about netlink packets structure and API see below in this lab.

Let's start with a simple exercise: create an `IPRoute` object and get IP
addresses. Most of pyroute2 classes, that provide some netlink API, create a
netlink socket and allocate some other resources. Because of the netlink
protocol, there may be not more than 1024 netlink sockets opened at the same
time per process ID, and it may be important to close objects if they're not
in use.

.. note::
   `IPRoute` methods always return iterables, as a response from the kernel always
   is a series of `[1..x]` messages.

To continue, run the exercise by pressing the `execute` button.

.. raw:: html
   :file: iproute_get_addr.html

Access messages data
~~~~~~~~~~~~~~~~~~~~

All the messages returned by `IPRoute` methods provide standard `nlmsg/nla`
API. Every message is a recursive dict-like structure, with fields accessible
via `__getitem__()`, and an optional NLA list accessible via `msg['attrs']`,
as you can see in the exercise above. If a message or NLA has `value` field
defined, this field is being returned by `getvalue()` method, otherwise
`getvalue()` returns the message or NLA itself. This makes simple type
NLA retrieval a bit more convenient.

These are methods to get fields and NLA values:

* `__getitem__('field')` -- return a field of this name
* `.get('field')`, `get('NLA_TYPE')`, `.get(('NLA_TYPE', ..., 'field'))` --
  the universal get method, see below
* `.getvalue()` -- return the `value` field, if defined, otherwise the object
  itself
* `.get_attr('NLA_TYPE')` -- get one NLA by the type; if there atr several
  NLA of the same type, get the first one in the list
* `.get_attrs('NLA_NAME')` -- get a list of NLA of this type

Some notes on `get()` method:

* returns a field or NLA value
* case insensitive for NLA types
* if NLA has `prefix` defined, it allows type notation both with and
  without the prefix, thus
  `get('IFLA_IFNAME') == get('IFNAME') == get('ifname')`
* the method first looks up for an NLA, and only then for a field of this
  name; if a message has both, like as `ndmsg` has a field `ifindex` and
  NLA type `NDA_IFINDEX`, then you can use `__getitem__()` and `getattr()`

.. raw:: html
   :file: iproute_get_attr.html
