import pytest
from net_tools import class_exists, filter_exists, qdisc_exists

from pyroute2 import protocols


@pytest.mark.asyncio
async def test_tc_get_qdiscs(
    async_ipr, test_link_ifname, test_link_index, nsname
):
    root_handle = '1:'
    await async_ipr.tc(
        'add',
        'tbf',
        index=test_link_index,
        handle=root_handle,
        rate=256,
        burst=256,
        latency=1,
    )
    assert qdisc_exists(
        ifname=test_link_ifname, handle=root_handle, rate=256, netns=nsname
    )
    assert (
        len(
            [
                x
                async for x in await async_ipr.get_qdiscs(
                    index=test_link_index
                )
            ]
        )
        == 1
    )
    await async_ipr.tc(
        'del', index=test_link_index, handle=root_handle, root=True
    )
    assert not qdisc_exists(
        ifname=test_link_ifname,
        handle=root_handle,
        rate=256,
        timeout=0.1,
        netns=nsname,
    )


@pytest.mark.asyncio
async def test_tc_htb(async_ipr, test_link_ifname, test_link_index, nsname):
    root_handle = '1:'
    root_options_default = '0x200000'
    await async_ipr.tc(
        'add',
        'htb',
        index=test_link_index,
        handle=root_handle,
        default=int(root_options_default, 16),
    )
    assert qdisc_exists(
        ifname=test_link_ifname,
        handle=root_handle,
        default=root_options_default,
        netns=nsname,
    )

    await async_ipr.tc(
        'add-class',
        'htb',
        index=test_link_index,
        handle='1:1',
        parent='1:0',
        rate='256kbit',
        burst=1024 * 6,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:1',
        root=True,
        netns=nsname,
    )

    await async_ipr.tc(
        'add-class',
        'htb',
        index=test_link_index,
        handle=0x10010,
        parent=0x10001,
        rate='192kbit',
        burst=1024 * 6,
        prio=1,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:10',
        parent='1:1',
        netns=nsname,
    )

    await async_ipr.tc(
        'add-class',
        'htb',
        index=test_link_index,
        handle='1:20',
        parent='1:1',
        rate='128kbit',
        burst=1024 * 6,
        prio=2,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:20',
        parent='1:1',
        netns=nsname,
    )

    await async_ipr.tc(
        'add-filter',
        'u32',
        index=test_link_index,
        handle='0:0',
        parent='1:0',
        prio=10,
        protocol=protocols.ETH_P_IP,
        target='1:10',
        keys=['0x0006/0x00ff+8', '0x0000/0xffc0+2'],
    )
    assert filter_exists(
        ifname=test_link_ifname,
        kind='u32',
        parent='1:',
        protocol='ip',
        match_value="6000000",
        match_mask="ff000000",
        netns=nsname,
    )

    await async_ipr.tc(
        'add-filter',
        'u32',
        index=test_link_index,
        handle=0,
        parent=0x10000,
        prio=10,
        protocol=protocols.ETH_P_IP,
        target=0x10020,
        keys=['0x5/0xf+0', '0x10/0xff+33'],
    )
    assert filter_exists(
        ifname=test_link_ifname,
        kind='u32',
        parent='1:',
        protocol='ip',
        match_value='10000000',
        match_mask='ff000000',
        netns=nsname,
    )

    # complementary delete commands
    await async_ipr.tc(
        'del-filter', index=test_link_index, handle='0:0', parent='1:0'
    )
    assert not filter_exists(
        ifname=test_link_ifname,
        kind='u32',
        parent='1:0',
        timeout=0.1,
        netns=nsname,
    )

    await async_ipr.tc(
        'del-class', index=test_link_index, handle='1:20', parent='1:1'
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:20',
        parent='1:1',
        timeout=0.1,
        netns=nsname,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:10',
        parent='1:1',
        netns=nsname,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:1',
        root=True,
        netns=nsname,
    )

    await async_ipr.tc(
        'del-class', index=test_link_index, handle='1:10', parent='1:1'
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:20',
        parent='1:1',
        timeout=0.1,
        netns=nsname,
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:10',
        parent='1:1',
        timeout=0.1,
        netns=nsname,
    )
    assert class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:1',
        root=True,
        netns=nsname,
    )

    await async_ipr.tc(
        'del-class', index=test_link_index, handle='1:1', parent='1:0'
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:20',
        parent='1:1',
        timeout=0.1,
        netns=nsname,
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:10',
        parent='1:1',
        timeout=0.1,
        netns=nsname,
    )
    assert not class_exists(
        ifname=test_link_ifname,
        kind='htb',
        handle='1:1',
        root=True,
        timeout=0.1,
        netns=nsname,
    )

    await async_ipr.tc(
        'del', index=test_link_index, handle=root_handle, root=True
    )
    assert not qdisc_exists(
        ifname=test_link_ifname, handle=root_handle, timeout=0.1, netns=nsname
    )
