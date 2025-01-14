"""Helper functions to build dhcp client messages."""

from pyroute2.dhcp.constants import bootp, dhcp
from pyroute2.dhcp.dhcp4msg import dhcp4msg


def discover(parameter_list: list[dhcp.Parameter]) -> dhcp4msg:
    return dhcp4msg(
        {
            'op': bootp.MessageType.BOOTREQUEST,
            'options': {
                'message_type': dhcp.MessageType.DISCOVER,
                'parameter_list': parameter_list,
            },
        }
    )


def request(
    requested_ip: str, server_id: str, parameter_list: list[dhcp.Parameter]
) -> dhcp4msg:
    return dhcp4msg(
        {
            'op': bootp.MessageType.BOOTREQUEST,
            'options': {
                'message_type': dhcp.MessageType.REQUEST,
                'requested_ip': requested_ip,
                'server_id': server_id,
                'parameter_list': parameter_list,
            },
        }
    )


def release(requested_ip: str, server_id: str) -> dhcp4msg:
    return dhcp4msg(
        {
            'op': bootp.MessageType.BOOTREQUEST,
            'options': {
                'message_type': dhcp.MessageType.RELEASE,
                'requested_ip': requested_ip,
                'server_id': server_id,
            },
        }
    )
