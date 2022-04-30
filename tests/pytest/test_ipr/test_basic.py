import pytest
import socket
from pyroute2 import IPRoute
from pyroute2.netlink import nlmsg


def test_context_manager():
    with IPRoute() as ipr:
        ipr.get_links()


def test_multiple_instances():
    ipr1 = IPRoute()
    ipr2 = IPRoute()
    ipr1.close()
    ipr2.close()


def test_close():
    ipr = IPRoute()
    ipr.get_links()
    ipr.close()
    # Shouldn't be able to use the socket after closing
    with pytest.raises(socket.error):
        ipr.get_links()


def test_fileno():
    ipr1 = IPRoute()
    ipr2 = IPRoute(fileno=ipr1.fileno())

    ipr1.close()
    with pytest.raises(OSError) as e:
        ipr2.get_links()
    assert e.value.errno == 9  # sendto -> Bad file descriptor

    with pytest.raises(OSError) as e:
        ipr2.close()
    assert e.value.errno == 9  # close -> Bad file descriptor


def test_get_policy_map(context):
    assert isinstance(context.ipr.get_policy_map(), dict)


def test_register_policy(context):
    context.ipr.register_policy(100, nlmsg)
    context.ipr.register_policy({101: nlmsg})
    context.ipr.register_policy(102, nlmsg)

    assert context.ipr.get_policy_map()[100] == nlmsg
    assert context.ipr.get_policy_map(101)[101] == nlmsg
    assert context.ipr.get_policy_map([102])[102] == nlmsg

    context.ipr.unregister_policy(100)
    context.ipr.unregister_policy([101])
    context.ipr.unregister_policy({102: nlmsg})

    assert 100 not in context.ipr.get_policy_map()
    assert 101 not in context.ipr.get_policy_map()
    assert 102 not in context.ipr.get_policy_map()
