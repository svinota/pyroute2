import struct

import pytest

from pyroute2.netlink.rtnl.ifinfmsg.plugins.can import can


@pytest.mark.parametrize('value', [0, 1, 0xFFFFFFFF])
def test_can_restart_encode(value):
    message = can()
    message['attrs'] = [('IFLA_CAN_RESTART', value)]
    message.encode()

    # Linux declares IFLA_CAN_RESTART (7) as NLA_U32, not NLA_FLAG.
    assert message.data[4:] == struct.pack('HHI', 8, 7, value)


@pytest.mark.parametrize('value', [0, 1, 0xFFFFFFFF])
def test_can_restart_decode(value):
    data = bytearray(struct.pack('HHHHI', 12, 0, 8, 7, value))
    message = can(data=data)
    message.decode()

    assert message.get_attr('IFLA_CAN_RESTART') == value
