.. parser:

.. raw:: html

   <span id="fold-sources" />

Netlink parser data flow
========================

NetlinkRequest
--------------

In order to run a query and get the response to it, `AsyncNetlinkSocket`
utilizes `NetlinkRequest` class that calculates required message flags,
allocates the sequence number, completes the query message, and encodes it.

When the message is about to being sent, `NetlinkRequest` first tries a
proxy, if any registered, and if `NetlinkRequest.proxy()` returns True
then `NetlinkRequest` stops processing, otherwise sends it using the
underlying socket.

`NetlinkRequest.response()` collects all the response packets for its
sequence number, buffered so far, and returns an async iterator over
the arrived response messages.

Marshal: get and run parsers
----------------------------

.. aafig::
    :scale: 80
    :textual:

    `                                                                  `
    data flow     struct        marshal
    +--------+    +--------+    +------------+
    |        |--->| bits   |    |            |
    |        |    |     32 |--->| length     | 4 bytes, offset 0
    |        |    +--------+    +------------+
    |        |    |     16 |--->| type-> key | 2 bytes, offset 4
    |        |    +--------+    +------------+
    |        |    |     16 |    | flags      | 2 bytes, offset 6
    |        |    +--------+    +------------+
    |        |    |        |    | `sequence` |
    |        |    |     32 |--->| `number`   | 4 bytes, offset 8
    |        |    +--------+    +------------+
    |        |    |        |
    |        |    |     32 |      pid (ignored by marshal)
    |        |    +--------+
    |        |    |        |

    |        |    |        |      payload (ignored by marshal)

    |        |    |        |    \                        /
    +--------+    +--------+     ---+--------------------
                                    |
                                    |
                                    |         / `marshal.msg_map = {`
                                    |        |
                                    |        |    key-> parser,
                                    |        |
                                    +--------+    key-> parser,
                                    |        |
                                    |        |    key-> parser,
                                    |        |
                                    |         \  `}`
                                    |
                                    v

Marshal should choose a proper parser depending on the `key`, `flags` and
`sequence_number`. By default it uses only `nlmsg->type` as the `key` and
`nlmsg->flags`, and there are several ways to customize getting parsers.

1. Use custom `key_format`, `key_offset` and `key_mask`. The latter is used
   to partially match the key, while `key_format` and `key_offset` are used
   to `struct.unpack()` the key from the raw netlink data.
2. You can overload `Marshal.get_parser()` and implement your own way to
   get parsers. A parser should be a simple function that gets only
   `data`, `offset` and `length` as arguments, and returns one dict compatible
   message.


.. aafig::
    :scale: 80
    :textual:

    `                                                                  `
                                    |
                                    |
                                    |
                                    |
                                    |
                                    v
              `if marshal.key_format is not None:`

                      `marshal.key_format`\
                                           |
                      `marshal.key_offset` +-- custom key
                                           |
                      `marshal.key_mask`  /

              `parser = marshal.get_parser(key, flags, sequence_number)`

              `msg = parser(data, offset, length)`

                                    |
                                    |
                                    |
                                    |
                                    |
                                    v

**pyroute2.netlink.nlsocket.Marshal**

.. code-include:: :func:`pyroute2.netlink.nlsocket.Marshal.parse`
    :language: python

The message parser routine must accept `data, offset, length` as the
arguments, and must return a valid `nlmsg` or `dict`, with the mandatory
fields, see the spec below. The parser can also return `None` which tells
the marshal to skip this message. The parser must parse data for one
message.

Mandatory message fields, expected by NetlinkSocketBase methods:

.. code-block:: python

    {
        'header': {
            'type': int,
            'flags': int,
            'error': None or NetlinkError(),
            'sequence_number': int,
        }
    }

.. aafig::
    :scale: 80
    :textual:

    `                                                                  `
                                    |
                                     
                                    |
                                     
                                    |
                                    v
              parsed msg
              +-------------------------------------------+
              | header                                    |
              |        `{`                                |
              |             `uint32 length,`              |
              |             `uint16 type,`                |
              |             `uint16 flags,`               |
              |             `uint32 sequence_number,`     |
              |             `uint32 pid,`                 |
              |        `}`                                |
              +- - - - - - - - - - - - - - - - - - - - - -+
              | data fields (optional)                    |
              |        `{`                                |
              |             `int field,`                  |
              |             `int field,`                  |
              |        `}`                                |
              | or                                        |
              |        `string field`                     |
              |                                           |
              +- - - - - - - - - - - - - - - - - - - - - -+
              | nla chain                                 |
              |                                           |
              |         +-------------------------------+ |
              |         | header                        | |
              |         |        `{`                    | |
              |         |             `uint16 length,`  | |
              |         |             `uint16 type,`    | |
              |         |        `}`                    | |
              |         +- - - - - - - - - - - - - - - -+ |
              |         | data fields (optional)        | |
              |         |                               | |
              |         |        ...                    | |
              |         |                               | |
              |         +- - - - - - - - - - - - - - - -+ |
              |         | nla chain                     | |
              |         |                               | |
              |         |        recursive              | |
              |         |                               | |
              |         +-------------------------------+ |
              |                                           |
              +-------------------------------------------+

Per-request parsers
-------------------

To assign a custom parser to a request/response communication, it is
enough to provide the parser function to the `NetlinkRequest` object.

An example is `IPRoute.get_default_routes()`, which could be slow on
systems with huge amounts of routes.

Instead of parsing every route record as `rtmsg`, this method assigns
a specific parser to its request. The custom parser doesn't parse records
blindly, but looks up only for default route records in the dump, and
then parses only matched records with the standard routine:

**pyroute2.iproute.linux.IPRoute**

.. code-include:: :func:`pyroute2.iproute.linux.RTNL_API.get_default_routes`
    :language: python

**pyroute2.iproute.parsers**

.. code-include:: :func:`pyroute2.iproute.parsers.default_routes`
    :language: python


NetlinkRequest: pick correct messages
-------------------------------------

The netlink protocol is asynchronous, so responses to several requests may
come simultaneously. Also the kernel may send broadcast messages that are
not responses, and have `sequence_number == 0`. As the response *may* contain
multiple messages, and *may* or *may not* be terminated by some specific type
of message, the task of returning relevant messages from the flow is a bit
complicated.

Let's look at an example:

.. aafig::
    :scale: 80
    :textual:

            +-----------+    +-----------+
            |  program  |    |   kernel  |
            +-----+-----+    +-----+-----+
                  |                |
                  |                |
                  |                | random broadcast
                  |<---------------|
                  |                |
                  |                |
    request seq 1 X                |
                  X--------------->X
                  X                X
                  X                X
                  X                X random broadcast
                  X<---------------X
                  X                X
                  X                X
                  X                X `response seq 1`
                  X<---------------X `flags: NLM_F_MULTI`
                  X                X
                  X                X
                  X                X random broadcast
                  X<---------------X
                  X                X
                  X                X
                  X                X `response seq 1`
                  X<---------------X `type: NLMSG_DONE`
                  X                |
                  |                |
                  v                v

The message flow on the diagram features `sequence_number == 0` broadcasts and
`sequence_number == 1` request and response packets. To complicate it even
further you can run a request with `sequence_number == 2` before the final
response with `sequence_number == 1` comes.

To handle that, pyroute2 protocol objects buffer all the messages, and
`NetlinkRequest` only gets the reponse.

**pyroute2.netlink.nlsocket.NetlinkRequest**

.. code-include:: :func:`pyroute2.netlink.nlsocket.NetlinkRequest.response`
    :language: python
