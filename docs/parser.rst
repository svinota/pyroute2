.. parser:

.. raw:: html

   <span id="fold-sources" />

Netlink parser (project)
========================


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

.. code-include:: :func:`pyroute2.netlink.nlsocket.Marshal.parse`
    :language: python
    :link-at-bottom:
    :link-to-source:

.. aafig::
    :scale: 80
    :textual:

    `                                                                  `
              `if marshal.key_format is not None:`

                      `marshal.key_format`\
                                           +--- custom key
                      `marshal.key_offset`/

              `parser = marshal.get_parser(key, flags, sequence_number)`

              `msg = parser(data, offset, length)`

                                    |
                                    |
                                    v

.. aafig::
    :scale: 80
    :textual:

    `                                                                  `
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
