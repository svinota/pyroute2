import struct

import pytest

from pyroute2 import IPRoute
from pyroute2.netlink import NLM_F_DUMP, NLM_F_REQUEST
from pyroute2.netlink.rtnl import (
    RTM_GETLINK,
    RTM_GETROUTE,
    RTM_NEWLINK,
    RTM_NEWROUTE,
)


@pytest.fixture
def ipr():
    with IPRoute() as iproute:
        yield iproute


test_config = (
    'name,argv,kwarg,msg_type,msg_flags',
    (
        (
            'link',
            ('get',),
            {'index': 1},
            (RTM_GETLINK, RTM_NEWLINK),
            NLM_F_REQUEST,
        ),
        (
            'link',
            ('dump',),
            {},
            (RTM_GETLINK, RTM_NEWLINK),
            NLM_F_DUMP | NLM_F_REQUEST,
        ),
        (
            'route',
            ('dump',),
            {},
            (RTM_GETROUTE, RTM_NEWROUTE),
            NLM_F_DUMP | NLM_F_REQUEST,
        ),
    ),
)


@pytest.mark.parametrize(*test_config)
def test_compile_call(ipr, name, argv, kwarg, msg_type, msg_flags):
    compiler_context = ipr.compile()
    data = getattr(ipr, name)(*argv, **kwarg)
    assert msg_type[0], msg_flags == struct.unpack_from(
        'HH', data[0], offset=4
    )
    compiler_context.close()
    assert ipr.compiled is None
    for msg in getattr(ipr, name)(*argv, **kwarg):
        assert msg['header']['type'] == msg_type[1]


@pytest.mark.parametrize(*test_config)
def test_compile_context_manager(ipr, name, argv, kwarg, msg_type, msg_flags):
    with ipr.compile():
        data = getattr(ipr, name)(*argv, **kwarg)
        assert msg_type[0], msg_flags == struct.unpack_from(
            'HH', data[0], offset=4
        )
    assert ipr.compiled is None
    for msg in getattr(ipr, name)(*argv, **kwarg):
        assert msg['header']['type'] == msg_type[1]
