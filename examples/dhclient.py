import sys
import select
from pprint import pprint
from pyroute2.dhcp import BOOTREQUEST
from pyroute2.dhcp import DHCPDISCOVER
from pyroute2.dhcp import DHCPOFFER
from pyroute2.dhcp import DHCPREQUEST
from pyroute2.dhcp import DHCPACK
from pyroute2.dhcp.dhcp4msg import dhcp4msg
from pyroute2.dhcp.dhcp4socket import DHCP4Socket


def req(s, poll, msg, expect):
    do_req = True
    xid = None

    while True:
        # get transaction id
        if do_req:
            xid = s.put(msg)['xid']
        # wait for response
        events = poll.poll(2)
        for (fd, event) in events:
            response = s.get()
            if response['xid'] != xid:
                do_req = False
                continue
            if response['options']['message_type'] != expect:
                raise Exception("DHCP protocol error")
            return response
        do_req = True


def action(ifname):
    s = DHCP4Socket(ifname)
    poll = select.poll()
    poll.register(s, select.POLLIN | select.POLLPRI)

    # DISCOVER
    discover = dhcp4msg({'op': BOOTREQUEST,
                         'chaddr': s.l2addr,
                         'options': {'message_type': DHCPDISCOVER,
                                     'parameter_list': [1, 3, 6, 12, 15, 28]}})
    reply = req(s, poll, discover, expect=DHCPOFFER)

    # REQUEST
    request = dhcp4msg({'op': BOOTREQUEST,
                        'chaddr': s.l2addr,
                        'options': {'message_type': DHCPREQUEST,
                                    'requested_ip': reply['yiaddr'],
                                    'server_id': reply['options']['server_id'],
                                    'parameter_list': [1, 3, 6, 12, 15, 28]}})
    reply = req(s, poll, request, expect=DHCPACK)
    pprint(reply)
    s.close()
    return reply


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ifname = sys.argv[1]
    else:
        ifname = 'eth0'
    action(ifname)
