# required by iw_scan_rsp.dump
import datetime  # noqa: F401
import json

import pytest

from pyroute2.common import load_dump
from pyroute2.netlink.nl80211 import MarshalNl80211
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl


@pytest.mark.parametrize(
    'sample,marshal',
    (
        ('test_unit/test_nlmsg/addrmsg_ipv4.dump', MarshalRtnl),
        ('test_unit/test_nlmsg/gre_01.dump', MarshalRtnl),
        ('test_unit/test_nlmsg/iw_info_rsp.dump', MarshalNl80211),
        ('test_unit/test_nlmsg/iw_scan_rsp.dump', MarshalNl80211),
    ),
)
def test_marshal(sample, marshal):
    parsed = []
    with open(sample, 'r') as buf:
        meta = {}
        parsed = marshal().parse(load_dump(buf, meta))
        if 'application/json' in meta:
            messages = json.loads(meta['application/json'])
        elif 'application/x-python-code' in meta:
            messages = eval(meta['application/x-python-code'])
        else:
            raise KeyError('sample messages not found')
    assert len(parsed) == len(messages)
    for parsed_msg, sample_value in zip(parsed, messages):
        sample_msg = type(parsed_msg)()
        sample_msg.setvalue(sample_value)
        assert parsed_msg == sample_msg
