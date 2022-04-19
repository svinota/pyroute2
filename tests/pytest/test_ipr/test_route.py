import errno
import pytest
import socket
from utils import require_kernel
from pyroute2 import IPRoute
from pyroute2 import NetlinkError


def test_route_get_target_strict_check(context):
    if not context.ipr.get_default_routes(table=254):
        pytest.skip('no default IPv4 routes')
    require_kernel(4, 20)
    with IPRoute(strict_check=True) as ip:
        rts = ip.get_routes(family=socket.AF_INET, dst='8.8.8.8', table=254)
        assert len(rts) > 0


def test_extended_error_on_route(context):
    require_kernel(4, 20)
    # specific flags, cannot use self.ip
    with IPRoute(ext_ack=True, strict_check=True) as ip:
        with pytest.raises(NetlinkError) as e:
            ip.route("get", dst="1.2.3.4", table=254, dst_len=0)
    assert abs(e.value.code) == errno.EINVAL
    # on 5.10 kernel, full message is 'ipv4: rtm_src_len and
    # rtm_dst_len must be 32 for IPv4'
    assert "rtm_dst_len" in str(e.value)
