import os
import socket

from pr2test.marks import require_root

from pyroute2 import NetlinkDumpInterrupted

pytestmark = [require_root()]


def test_mass_ipv6(context):
    #
    ipv6net = context.new_ip6net
    base = str(ipv6net.network) + '{0}'
    limit = int(os.environ.get('PYROUTE2_SLIMIT', '0x800'), 16)
    index, ifname = context.default_interface

    # add addresses
    for idx in range(limit):
        context.ipr.addr(
            'add',
            index=index,
            family=socket.AF_INET6,
            address=base.format(hex(idx)[2:]),
            prefixlen=48,
        )

    # assert addresses in two steps, to ease debug
    addrs = []
    for _ in range(3):
        try:
            addrs = context.ipr.get_addr(family=socket.AF_INET6)
            break
        except NetlinkDumpInterrupted:
            pass
    else:
        raise Exception('could not dump addresses')
    assert len(addrs) >= limit
