.. parser:

.. raw:: html

   <span id="fold-sources" />

Netlink parser data flow
========================

NetlinkSocketBase: receive the data
-----------------------------------

When `NetlinkSocketBase` receives the data from a netlink socket, it can do it
in two ways:

1. get data directly with `socket.recv()` or `socket.recv_into()`
2. run a buffer thread that receives the data asap and leaves in the
   `buffer_queue` to be consumed later by `recv()` or `recv_into()`

`NetlinkSocketBase` implements these two receive methods, that choose
the data source -- directly from the socket or from `buffer_queue` --
depending on the `buffer_thread` property:

**pyroute2.netlink.nlsocket.NetlinkSocketBase**

.. code-include:: :func:`pyroute2.netlink.nlsocket.NetlinkSocketBase.recv`
    :language: python

.. code-include:: :func:`pyroute2.netlink.nlsocket.NetlinkSocketBase.recv_into`
    :language: python

.. code-include:: :func:`pyroute2.netlink.nlsocket.NetlinkSocketBase.buffer_thread_routine`
    :language: python

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

Marshal: get and run parsers
----------------------------

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

NetlinkSocketBase: pick correct messages
----------------------------------------

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

To handle that, `NetlinkSocketBase.get()` buffers all the irrelevant messages,
returns ones with only the requested `sequence_number`, and uses locks to wait
on the resource.

The current implementation is relatively complicated and will be changed in
the future.

**pyroute2.netlink.nlsocket.NetlinkSocketBase**

.. code-include:: :func:`pyroute2.netlink.nlsocket.NetlinkSocketBase.get`
    :language: python
