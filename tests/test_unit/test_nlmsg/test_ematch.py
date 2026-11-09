import struct

import pytest

from pyroute2.netlink.rtnl import RTM_NEWTFILTER
from pyroute2.netlink.rtnl.iprsocket import MarshalRtnl
from pyroute2.netlink.rtnl.tcmsg.common_ematch import get_tcf_ematches


def nla(kind, payload):
    length = len(payload) + 4
    return struct.pack('=HH', length, kind) + payload + b'\0' * (-length % 4)


def basic_filter(matches):
    # Kernel wire layout of tc's "basic match ipset(...)" (issue #1248).
    return filter_with_ematches(
        [
            (8, struct.pack('=HBB', index, dimension, modes), flags)
            for index, dimension, modes, flags in matches
        ]
    )


def filter_with_ematches(matches):
    entries = b''.join(
        nla(i + 1, struct.pack('=HHHH', 0, kind, flags, 0) + payload)
        for i, (kind, payload, flags) in enumerate(matches)
    )
    tree = nla(1, struct.pack('=HH', len(matches), 0)) + nla(2, entries)
    attrs = nla(1, b'basic\0') + nla(2, nla(2, tree))
    payload = struct.pack('=BBHiIII', 0, 0, 0, 1, 1, 0x10000, 0x300) + attrs
    return (
        struct.pack('=IHHII', len(payload) + 16, RTM_NEWTFILTER, 2, 1, 0)
        + payload
    )


@pytest.mark.parametrize(
    'matches', [[(0, 1, 2, 0)], [(3, 2, 2, 1), (17, 1, 0, 0)]]
)
def test_ipset_ematch_dump(matches, caplog):
    (message,) = MarshalRtnl().parse(basic_filter(matches))
    tree = message.get_attr('TCA_OPTIONS').get_attr('TCA_BASIC_EMATCHES')
    assert tree.get_attr('TCA_EMATCH_TREE_HDR')['nmatches'] == len(matches)
    decoded = tree.get_attr('TCA_EMATCH_TREE_LIST')
    assert len(decoded) == len(matches)
    for actual, (index, dimension, modes, flags) in zip(decoded, matches):
        assert actual['kind'] == 8
        assert actual['flags'] == flags
        assert actual['opt']['ip_set_index'] == index
        assert actual['opt']['ip_set_dim'] == dimension
        assert actual['opt']['ip_set_flags'] == modes
    assert not caplog.records
    assert message['index'] == 1
    assert message['parent'] == 0x10000


def test_ipset_ematch_encoding():
    # Adding decoding support must preserve the public tc encoder's output.
    result = get_tcf_ematches(
        {'match': [{'kind': 'ipset', 'index': 17, 'mode': 'src,dst'}]}
    )
    match = dict(result['attrs'])['TCA_EMATCH_TREE_LIST'][0]
    assert match['kind'] == 8
    assert match['opt'] == struct.pack('=HBB', 17, 2, 2)


def test_cmp_ematch_dump(caplog):
    packet = filter_with_ematches(
        [(1, struct.pack('=IIHBB', 0x1234, 0xFFFF, 12, 2, 1), 0)]
    )
    (message,) = MarshalRtnl().parse(packet)
    tree = message.get_attr('TCA_OPTIONS').get_attr('TCA_BASIC_EMATCHES')
    decoded = tree.get_attr('TCA_EMATCH_TREE_LIST')
    assert len(decoded) == 1
    assert decoded[0]['opt']['val'] == 0x1234
    assert decoded[0]['opt']['mask'] == 0xFFFF
    assert decoded[0]['opt']['align'] == 'TCF_EM_ALIGN_U16'
    assert decoded[0]['opt']['layer'] == 'TCF_LAYER_NETWORK'
    assert not caplog.records


def test_empty_ematch_dump(caplog):
    (message,) = MarshalRtnl().parse(filter_with_ematches([]))
    tree = message.get_attr('TCA_OPTIONS').get_attr('TCA_BASIC_EMATCHES')
    assert tree.get_attr('TCA_EMATCH_TREE_LIST') == []
    assert not caplog.records


def test_short_ipset_ematch_remains_raw(caplog):
    # Preserve the parser's fallback on an incomplete kernel attribute.
    packet = filter_with_ematches([(8, b'\0', 0)])
    (message,) = MarshalRtnl().parse(packet)
    tree = message.get_attr('TCA_OPTIONS').get_attr('TCA_BASIC_EMATCHES')
    assert isinstance(tree.get_attr('TCA_EMATCH_TREE_LIST'), bytes)
    assert caplog.records


def test_meta_ematch_dump(caplog):
    # "meta(vlan mask 0xfff eq 1337)" from the second issue reproducer.
    payload = (
        nla(1, struct.pack('=HBBHH', 0x102E, 0, 0, 0x1000, 0))
        + nla(2, struct.pack('=I', 0xFFF))
        + nla(3, struct.pack('<I', 1337))
    )
    (message,) = MarshalRtnl().parse(filter_with_ematches([(4, payload, 0)]))
    tree = message.get_attr('TCA_OPTIONS').get_attr('TCA_BASIC_EMATCHES')
    decoded = tree.get_attr('TCA_EMATCH_TREE_LIST')
    assert len(decoded) == 1
    options = decoded[0]['opt']
    assert (
        options.get_attr('TCA_EM_META_HDR')['kind'] == 'TCF_META_ID_VLAN_TAG'
    )
    assert options.get_attr('TCA_EM_META_LVALUE') == 0xFFF
    assert options.get_attr('TCA_EM_META_RVALUE') == 1337
    assert not caplog.records
