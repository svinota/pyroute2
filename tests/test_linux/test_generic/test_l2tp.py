import errno
import time

import pytest

from pyroute2 import L2tp, NetlinkError


@pytest.fixture
def l2ctx(context):
    try:
        context.l2tp = L2tp()
    except NetlinkError as e:
        if e.code == errno.ENOENT:
            pytest.skip('L2TP netlink API not available')
        raise
    context.local_ip = context.get_ipaddr(r=0)
    context.remote_ip = context.get_ipaddr(r=1)
    context.l2tpeth0 = context.new_ifname
    context.ndb.interfaces[context.default_interface.ifname].add_ip(
        f'{context.local_ip}/24'
    ).commit()
    yield context
    try:
        context.l2tp.delete_session(tunnel_id=2324, session_id=3435)
    except Exception:
        pass
    try:
        context.l2tp.delete_tunnel(tunnel_id=2324)
    except Exception:
        pass
    context.l2tp.close()


def test_complete(l2ctx):

    # 1. create tunnel
    l2ctx.l2tp.create_tunnel(
        tunnel_id=2324,
        peer_tunnel_id=2425,
        remote=l2ctx.remote_ip,
        local=l2ctx.local_ip,
        udp_dport=32000,
        udp_sport=32000,
        encap="udp",
    )
    tunnel = l2ctx.l2tp.get_tunnel(tunnel_id=2324)
    assert tunnel[0].get_attr("L2TP_ATTR_CONN_ID") == 2324
    assert tunnel[0].get_attr("L2TP_ATTR_PEER_CONN_ID") == 2425
    assert tunnel[0].get_attr("L2TP_ATTR_IP_DADDR") == l2ctx.remote_ip
    assert tunnel[0].get_attr("L2TP_ATTR_IP_SADDR") == l2ctx.local_ip
    assert tunnel[0].get_attr("L2TP_ATTR_UDP_DPORT") == 32000
    assert tunnel[0].get_attr("L2TP_ATTR_UDP_SPORT") == 32000
    assert tunnel[0].get_attr("L2TP_ATTR_ENCAP_TYPE") == 0  # 0 == UDP
    assert tunnel[0].get_attr("L2TP_ATTR_DEBUG") == 0

    # 2. create session
    l2ctx.l2tp.create_session(
        tunnel_id=2324,
        session_id=3435,
        peer_session_id=3536,
        ifname=l2ctx.l2tpeth0,
    )
    session = l2ctx.l2tp.get_session(tunnel_id=2324, session_id=3435)
    assert session[0].get_attr("L2TP_ATTR_SESSION_ID") == 3435
    assert session[0].get_attr("L2TP_ATTR_PEER_SESSION_ID") == 3536
    assert session[0].get_attr("L2TP_ATTR_DEBUG") == 0

    # setting up DEBUG -> 95, operation not supported; review the test
    # # 3. modify session
    # l2ctx.l2tp.modify_session(tunnel_id=2324, session_id=3435, debug=True)
    # session = l2ctx.l2tp.get_session(tunnel_id=2324, session_id=3435)
    # assert session[0].get_attr("L2TP_ATTR_DEBUG") == 1

    # setting up DEBUG -> 95, operation not supported; review the test
    # # 4. modify tunnel
    # l2ctx.l2tp.modify_tunnel(tunnel_id=2324, debug=True)
    # tunnel = l2ctx.l2tp.get_tunnel(tunnel_id=2324)
    # assert tunnel[0].get_attr("L2TP_ATTR_DEBUG") == 1

    # 5. destroy session
    l2ctx.l2tp.delete_session(tunnel_id=2324, session_id=3435)
    for _ in range(5):
        try:
            assert not l2ctx.l2tp.get_session(tunnel_id=2324, session_id=3435)
        except AssertionError:
            time.wait(0.1)
            continue
        break
    else:
        raise Exception('could not remove L2TP session')

    # 6. destroy tunnel
    l2ctx.l2tp.delete_tunnel(tunnel_id=2324)
    for _ in range(5):
        try:
            assert not l2ctx.l2tp.get_tunnel(tunnel_id=2324)
        except AssertionError:
            time.wait(0.1)
            continue
        break
    else:
        raise Exception('could not remove L2TP tunnel')
