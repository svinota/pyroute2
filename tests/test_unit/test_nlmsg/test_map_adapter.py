import pytest

from pyroute2.netlink import NlaMapAdapter, NlaSpec, nlmsg_atoms, rtnl
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.marshal import MarshalRtnl

sample_data_ipaddr = (
    b'L\x00\x00\x00\x14\x00\x02\x00\xff\x00\x00\x00\xfb\x8d\x00\x00\x02\x08'
    b'\x80\xfe\x01\x00\x00\x00\x08\x00\x01\x00\x7f\x00\x00\x01\x08\x00\x02\x00'
    b'\x7f\x00\x00\x01\x07\x00\x03\x00lo\x00\x00\x08\x00\x08\x00\x80\x00\x00'
    b'\x00\x14\x00\x06\x00\xff\xff\xff\xff\xff\xff\xff\xffQ\x00\x00\x00Q\x00'
    b'\x00\x00'
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
    assert (
        msg.get_attr('IFA_NLA_6')  # IFA_CACHEINFO
        == 'ff:ff:ff:ff:ff:ff:ff:ff:51:00:00:00:51:00:00:00'
    )
    assert msg.get_attr('IFA_NLA_8') == '80:00:00:00'  # IFA_FLAGS
