import socket
import struct

import pytest
from pr2test.marks import require_root

pytestmark = [require_root()]


def test_flush_rules(context):
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    init = len(context.ipr.get_rules(family=socket.AF_INET))
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 0
    context.ipr.rule('add', table=10, priority=110)
    context.ipr.rule('add', table=15, priority=150, action='FR_ACT_PROHIBIT')
    context.ipr.rule('add', table=20, priority=200, src=ifaddr1)
    context.ipr.rule('add', table=25, priority=250, dst=ifaddr2)
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 4
    assert len(context.ipr.get_rules(src=ifaddr1)) == 1
    assert len(context.ipr.get_rules(dst=ifaddr2)) == 1
    context.ipr.flush_rules(
        family=socket.AF_INET, priority=lambda x: 100 < x < 500
    )
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 0
    assert len(context.ipr.get_rules(src=ifaddr1)) == 0
    assert len(context.ipr.get_rules(dst=ifaddr2)) == 0
    assert len(context.ipr.get_rules(family=socket.AF_INET)) == init


def test_basic(context):
    context.ipr.rule('add', table=10, priority=32000)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32000
                and x.get_attr('FRA_TABLE') == 10
            ]
        )
        == 1
    )
    context.ipr.rule('delete', table=10, priority=32000)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32000
                and x.get_attr('FRA_TABLE') == 10
            ]
        )
        == 0
    )


def test_fwmark(context):
    context.ipr.rule('add', table=15, priority=32006, fwmark=10)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
            ]
        )
        == 1
    )
    context.ipr.rule('delete', table=15, priority=32006, fwmark=10)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
            ]
        )
        == 0
    )


def test_fwmark_mask_normalized(context):
    context.ipr.rule('add', table=15, priority=32006, fwmark=10, fwmask=20)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
                and x.get_attr('FRA_FWMASK')
            ]
        )
        == 1
    )
    context.ipr.rule('delete', table=15, priority=32006, fwmark=10, fwmask=20)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
                and x.get_attr('FRA_FWMASK')
            ]
        )
        == 0
    )


def test_fwmark_mask_raw(context):
    context.ipr.rule('add', table=15, priority=32006, fwmark=10, FRA_FWMASK=20)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
                and x.get_attr('FRA_FWMASK')
            ]
        )
        == 1
    )
    context.ipr.rule(
        'delete', table=15, priority=32006, fwmark=10, FRA_FWMASK=20
    )
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32006
                and x.get_attr('FRA_TABLE') == 15
                and x.get_attr('FRA_FWMARK')
                and x.get_attr('FRA_FWMASK')
            ]
        )
        == 0
    )


def test_bad_table(context):
    with pytest.raises(struct.error):
        context.ipr.rule('add', table=-1, priority=32000)


def test_big_table(context):
    context.ipr.rule('add', table=1024, priority=32000)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32000
                and x.get_attr('FRA_TABLE') == 1024
            ]
        )
        == 1
    )
    context.ipr.rule('delete', table=1024, priority=32000)
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32000
                and x.get_attr('FRA_TABLE') == 1024
            ]
        )
        == 0
    )


def test_src_dst(context):
    context.ipr.rule(
        'add',
        table=17,
        priority=32005,
        src='10.0.0.0',
        src_len=24,
        dst='10.1.0.0',
        dst_len=24,
    )
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32005
                and x.get_attr('FRA_TABLE') == 17
                and x.get_attr('FRA_SRC') == '10.0.0.0'
                and x.get_attr('FRA_DST') == '10.1.0.0'
                and x['src_len'] == 24
                and x['dst_len'] == 24
            ]
        )
        == 1
    )
    context.ipr.rule(
        'del',
        table=17,
        priority=32005,
        src='10.0.0.0',
        src_len=24,
        dst='10.1.0.0',
        dst_len=24,
    )
    assert (
        len(
            [
                x
                for x in context.ipr.get_rules()
                if x.get_attr('FRA_PRIORITY') == 32005
                and x.get_attr('FRA_TABLE') == 17
                and x.get_attr('FRA_SRC') == '10.0.0.0'
                and x.get_attr('FRA_DST') == '10.1.0.0'
                and x['src_len'] == 24
                and x['dst_len'] == 24
            ]
        )
        == 0
    )
