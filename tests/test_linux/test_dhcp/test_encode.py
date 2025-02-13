from typing import Any

import pytest

from pyroute2.dhcp.dhcp4msg import dhcp4msg
from pyroute2.dhcp.enums import dhcp


@pytest.mark.parametrize(
    ('option_name', 'option_value'),
    (
        ('name_server', ['1.1.1.2', '2.2.2.2']),
        ('lease_time', -1),
        ('host_name', b'some computer'),
        ('max_msg_size', 1500),
        ('subnet_mask', '255.255.255.0'),
    ),
)
def test_encode_decode_options(option_name: str, option_value: Any):
    msg = dhcp4msg(
        {
            'options': {
                'message_type': dhcp.MessageType.ACK,
                option_name: option_value,
            }
        }
    )
    data = msg.encode().buf
    decoded_msg = dhcp4msg(buf=data).decode()
    assert (
        decoded_msg['options'][option_name]
        == msg['options'][option_name]
        == option_value
    )
