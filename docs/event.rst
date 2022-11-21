.. _event:

Generic netlink events protocols
================================

The only available method for the event sockets is `get()` -- it returns
an iterator over broadcasted messages, following the generic pyroute2 API.
Even though the event protocols provide one message per `recv()`.

No manual `bind()` or `discovery()` required -- the event sockets run
these methods authomatically.

Please keep in mind that you have to consume all the incoming messages
in time, otherwise a buffer overflow happens on the socket and the only
way to fix that is to `close()` the failed socket and to open a new one.

ACPI events
-----------

.. automodule:: pyroute2.netlink.event.acpi_event

Disk quota events
-----------------

.. automodule:: pyroute2.netlink.event.dquot
