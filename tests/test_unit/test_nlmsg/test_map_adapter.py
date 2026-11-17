import struct

import pytest

from pyroute2.netlink import NlaMapAdapter, NlaSpec, nlmsg_atoms, rtnl
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.marshal import MarshalRtnl

# Netlink headers and integer attributes use the host's byte order.
# Keep the raw wire fixture independent of the encoder under test.
sample_data_ipaddr = b''.join(
    (
        struct.pack('=IHHII', 76, rtnl.RTM_NEWADDR, 2, 255, 36347),
        struct.pack('=BBBBI', 2, 8, 128, 254, 1),
        struct.pack('=HH4s', 8, 1, b'\x7f\x00\x00\x01'),
        struct.pack('=HH4s', 8, 2, b'\x7f\x00\x00\x01'),
        struct.pack('=HH3sx', 7, 3, b'lo\x00'),
        struct.pack('=HHI', 8, 8, 128),
        struct.pack('=HH4I', 20, 6, 0xFFFFFFFF, 0xFFFFFFFF, 81, 81),
    )
)


class ifaddrmsg_default_decode(ifaddrmsg):
    # same function will be used both for decode and encode
    nla_map = NlaMapAdapter(
        lambda x: NlaSpec(nlmsg_atoms.hex, x, f'IFA_NLA_{x}')
    )


class ifaddrmsg_dict_decode(ifaddrmsg):
    # define separate decode / encode adapters
    nla_map = {
        'decode': NlaMapAdapter(
            lambda x: NlaSpec(nlmsg_atoms.hex, x, f'IFA_NLA_{x}')
        ),
        'encode': None,
    }


@pytest.mark.parametrize(
    'nlmsg_class,data',
    (
        (ifaddrmsg_default_decode, sample_data_ipaddr),
        (ifaddrmsg_dict_decode, sample_data_ipaddr),
    ),
    ids=['default_decode', 'dict_decode'],
)
def test_decode_adapter(nlmsg_class, data):
    marshal = MarshalRtnl()
    marshal.msg_map[rtnl.RTM_NEWADDR] = nlmsg_class
    msgs = tuple(marshal.parse(data))
    msg = msgs[0]
    assert len(msgs) == 1
    assert msg.get_attr('IFA_NLA_1') == '7f:00:00:01'  # IFA_ADDRESS
    assert msg.get_attr('IFA_NLA_2') == '7f:00:00:01'  # IFA_LOCAL
    assert msg.get_attr('IFA_NLA_3') == '6c:6f:00'  # IFA_LABEL
    assert msg.get_attr('IFA_NLA_6') == struct.pack(  # IFA_CACHEINFO
        '=4I', 0xFFFFFFFF, 0xFFFFFFFF, 81, 81
    ).hex(':')
    assert msg.get_attr('IFA_NLA_8') == struct.pack('=I', 128).hex(':')
