# required by iw_scan_rsp.dump
import datetime  # noqa: F401
import json

import pytest

from pyroute2.common import load_dump
from pyroute2.netlink.nl80211 import MarshalNl80211
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl


def run_using_marshal(sample, marshal):
    parsed = []
    with open(sample, 'r') as buf:
        meta = {}
        parsed = marshal.parse(load_dump(buf, meta))
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
        assert sample_msg == parsed_msg


@pytest.mark.parametrize(
    'sample,marshal',
    (
        ('test_unit/test_nlmsg/addrmsg_ipv4.dump', MarshalRtnl()),
        ('test_unit/test_nlmsg/gre_01.dump', MarshalRtnl()),
        ('test_unit/test_nlmsg/iw_info_rsp.dump', MarshalNl80211()),
        ('test_unit/test_nlmsg/iw_scan_rsp.dump', MarshalNl80211()),
    ),
)
def test_marshal(sample, marshal):
    return run_using_marshal(sample, marshal)


@pytest.mark.parametrize(
    'sample,marshal',
    (
        ('test_unit/test_nlmsg/addrmsg_ipv4.dump', MarshalRtnl()),
        ('test_unit/test_nlmsg/gre_01.dump', MarshalRtnl()),
    ),
)
def test_custom_key(sample, marshal):
    # the header:
    #
    #  uint32 length
    #  uint16 type
    #  ...
    #
    # e.g.:
    # 4c:00:00:00:14:00:...
    #
    # this test uses:
    marshal.key_format = 'I'  # 4 bytes LE as the key
    marshal.key_offset = 2  # but with offset 2
    marshal.key_mask = 0xFFFF0000  # ignore 2 lower bytes:
    #
    # example 1:
    # offset 2 -> 00:00:14:00
    # format I -> 0x140000
    # & mask -> 0x140000
    #
    # example 2:
    # offset 2 -> 01:02:14:00
    # format I -> 0x140201
    # & mask -> 0x140000
    #
    # fix msg map to use new keys:
    for key, value in tuple(marshal.msg_map.items()):
        marshal.msg_map[key << 16] = value
    #
    # ok, now should run
    return run_using_marshal(sample, marshal)


@pytest.mark.parametrize(
    'sample,marshal',
    (
        ('test_unit/test_nlmsg/addrmsg_ipv4.dump', MarshalRtnl()),
        ('test_unit/test_nlmsg/gre_01.dump', MarshalRtnl()),
    ),
)
def test_custom_key_fail(sample, marshal):
    # same as above, but don't fix the map -> must fail
    marshal.key_format = 'I'
    marshal.key_offset = 2
    marshal.key_mask = 0xFFFF0000
    with pytest.raises(AssertionError):
        return run_using_marshal(sample, marshal)
