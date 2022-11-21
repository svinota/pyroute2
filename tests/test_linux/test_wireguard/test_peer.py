from socket import AF_INET, AF_INET6

from pr2test.marks import require_root

pytestmark = [require_root()]


def test_peer_ipv4(context):

    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    port = 9999
    listen = 2525
    peer_ip_1 = context.new_ipaddr
    peer_ip_2 = context.new_ipaddr
    allowed_ip_1 = str(context.ipnets[1])
    allowed_ip_2 = str(context.ipnets[2])

    (
        context.ndb.interfaces.create(ifname=ifname, kind='wireguard')
        .add_ip(f'{ipaddr}/24')
        .set('state', 'up')
        .commit()
    )

    peer_1 = {
        'public_key': 'TGFHcm9zc2VCaWNoZV9DJ2VzdExhUGx1c0JlbGxlPDM=',
        'endpoint_addr': peer_ip_1,
        'endpoint_port': port,
        'persistent_keepalive': 15,
        'allowed_ips': [f'{allowed_ip_1}'],
    }

    peer_2 = {
        'public_key': 'AGFHcm9zc2VCaWNoZV9DJ2VzdExhUGx1c0JlbGxlPDM=',
        'endpoint_addr': peer_ip_2,
        'endpoint_port': port,
        'persistent_keepalive': 15,
        'allowed_ips': [f'{allowed_ip_2}'],
    }

    (
        context.wg.set(
            ifname,
            private_key='RCdhcHJlc0JpY2hlLEplU2VyYWlzTGFQbHVzQm9ubmU=',
            fwmark=0x1337,
            listen_port=listen,
            peer=peer_1,
        )
    )

    (
        context.wg.set(
            ifname,
            private_key='RCdhcHJlc0JpY2hlLEplU2VyYWlzTGFQbHVzQm9ubmU=',
            fwmark=0x1337,
            listen_port=listen,
            peer=peer_2,
        )
    )

    for peer in context.wg.info(ifname)[0].get_attr('WGDEVICE_A_PEERS'):
        endpoint = peer.get_attr('WGPEER_A_ENDPOINT')
        allowed = peer.get_attr('WGPEER_A_ALLOWEDIPS')
        assert endpoint['family'] == AF_INET
        assert endpoint['port'] == port
        assert endpoint['addr'] in (peer_ip_1, peer_ip_2)
        assert allowed[0]['addr'] in (allowed_ip_1, allowed_ip_2)


def test_peer_ipv6(context):

    ifname = context.new_ifname
    ipaddr = context.new_ipaddr
    port = 9999
    listen = 2525
    peer_ip_1 = '::fa'
    peer_ip_2 = '::fb'
    allowed_ip_1 = 'fa::/64'
    allowed_ip_2 = 'fb::/64'

    (
        context.ndb.interfaces.create(ifname=ifname, kind='wireguard')
        .add_ip(f'{ipaddr}/24')
        .set('state', 'up')
        .commit()
    )

    peer_1 = {
        'public_key': 'TGFHcm9zc2VCaWNoZV9DJ2VzdExhUGx1c0JlbGxlPDM=',
        'endpoint_addr': peer_ip_1,
        'endpoint_port': port,
        'persistent_keepalive': 15,
        'allowed_ips': [f'{allowed_ip_1}'],
    }

    peer_2 = {
        'public_key': 'AGFHcm9zc2VCaWNoZV9DJ2VzdExhUGx1c0JlbGxlPDM=',
        'endpoint_addr': peer_ip_2,
        'endpoint_port': port,
        'persistent_keepalive': 15,
        'allowed_ips': [f'{allowed_ip_2}'],
    }

    (
        context.wg.set(
            ifname,
            private_key='RCdhcHJlc0JpY2hlLEplU2VyYWlzTGFQbHVzQm9ubmU=',
            fwmark=0x1337,
            listen_port=listen,
            peer=peer_1,
        )
    )

    (
        context.wg.set(
            ifname,
            private_key='RCdhcHJlc0JpY2hlLEplU2VyYWlzTGFQbHVzQm9ubmU=',
            fwmark=0x1337,
            listen_port=listen,
            peer=peer_2,
        )
    )

    for peer in context.wg.info(ifname)[0].get_attr('WGDEVICE_A_PEERS'):
        endpoint = peer.get_attr('WGPEER_A_ENDPOINT')
        allowed = peer.get_attr('WGPEER_A_ALLOWEDIPS')
        assert endpoint['family'] == AF_INET6
        assert endpoint['port'] == port
        assert endpoint['addr'] in (peer_ip_1, peer_ip_2)
        assert allowed[0]['addr'] in (allowed_ip_1, allowed_ip_2)
