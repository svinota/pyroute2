IPRoute -- work with interfaces, addresses and routes
-----------------------------------------------------

.. _dmesg:


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
time per process ID, and it may be important to close object if it's not in
use.

.. note::
   `IPRoute` methods always return iterables, as a response from the kernel always
   is a series of `[1..x]` messages.

To continue, run the exercise by pressing the `execute & check` button.

.. raw:: html
   :file: iproute_get_addr.html

Access messages data
~~~~~~~~~~~~~~~~~~~~

All the messages returned by `IPRoute` methods provide standard `nlmsg` API.
Every message is a dict-like structure, with fields accessible via
`__getitem__()`, and an optional NLA list, accessible via `msg['attrs']`, as
you can see in the exercise above.

Beside of the raw dict API, there is a set of convenience methods to access
the data:

* `.get_attr('NLA_NAME')` -- get one NLA
* `.get_attrs('NLA_NAME')` -- same, but get all NLAs with this name
* `.get_nested('NLA_NAME', 'NESTED_NAME', ...)` -- get a nested NLA
* `.get('name')`, `.get(('name', 'nested', ...))` -- a universal get method

The next exercise shows some of them:

.. raw:: html
   :file: iproute_get_attr.html
