Description
-----------

This is the data directory for the parser testing.

The test module: `general/test_parser.py`

Data format
-----------

The data files can be in two formats. The strace hex dump:
```
    \x00\x00\x00...
```

And the pyroute2 hex dump:
```
    00:00:00...
```

When the data file gets loaded, all the spaces, comments and
new lines are ignored. There can be several packets in the
same file, the parser deals with it. Comments should start
with `#` or `;`:
```
    # field one
    00:00:00
    # field two
    00:00:00
    ...
```

All the data after `.` is also ignored. It can be used to
provide detailed descriptions of the file after the dump
data:
```
    \x00\x00\x00...
    .
    Here goes the data description
```

How to collect
--------------

To collect the data, one can use either of two approaches.
First, use strace:
```
    $ strace -e trace=network -f -x -s 4096 netlink_utility
    ...
    sendto(3, "\x28\x00\x00\x00\x12\x00\x01\x03\x67\x9a..."... )
```

Then just copy and paste to the data file strings from `sendto()`
and `recvmsg()` calls.

Or one can use packets parsed with pyroute2:
```
    >>> from pyroute2 import IPRoute
    >>> from pyroute2.common import hexdump
    >>> ipr = IPRoute()
    >>> pkts = ipr.get_addr()
    >>> hexdump(pkts[0].raw)
    '4c:00:00:00:14:00:02:00:ff:00:00:00:...'
```
