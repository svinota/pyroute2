import pytest
from pr2test.tools import (
    class_exists,
    filter_exists,
    interface_exists,
    qdisc_exists,
)

from pyroute2 import protocols


async def util_link_add(async_ipr):
    ifname = async_ipr.register_temporary_ifname()
    await async_ipr.link('add', ifname=ifname, kind='dummy', state='up')
    assert interface_exists(ifname)
    return ifname


@pytest.mark.asyncio
async def test_tc_htb(async_ipr):
    root_handle = '1:'
    root_options_default = '0x200000'
    ifname = await util_link_add(async_ipr)
    (link,) = await async_ipr.link('get', ifname=ifname)
    index = link['index']
    await async_ipr.tc(
        'add',
        'htb',
        index=index,
        handle=root_handle,
        default=int(root_options_default, 16),
    )
    assert qdisc_exists(
        ifname=ifname, handle=root_handle, default=root_options_default
    )

    await async_ipr.tc(
        'add-class',
        'htb',
        index=index,
        handle='1:1',
        parent='1:0',
        rate='256kbit',
        burst=1024 * 6,
    )
    assert class_exists(ifname=ifname, kind='htb', handle='1:1', root=True)

    await async_ipr.tc(
        'add-class',
        'htb',
        index=index,
        handle=0x10010,
        parent=0x10001,
        rate='192kbit',
        burst=1024 * 6,
        prio=1,
    )
    assert class_exists(ifname=ifname, kind='htb', handle='1:10', parent='1:1')

    await async_ipr.tc(
        'add-class',
        'htb',
        index=index,
        handle='1:20',
        parent='1:1',
        rate='128kbit',
        burst=1024 * 6,
        prio=2,
    )
    assert class_exists(ifname=ifname, kind='htb', handle='1:20', parent='1:1')

    await async_ipr.tc(
        'add-filter',
        'u32',
        index=index,
        handle='0:0',
        parent='1:0',
        prio=10,
        protocol=protocols.ETH_P_IP,
        target='1:10',
        keys=['0x0006/0x00ff+8', '0x0000/0xffc0+2'],
    )
    assert filter_exists(
        ifname=ifname,
        kind='u32',
        parent='1:',
        protocol='ip',
        match_value="6000000",
        match_mask="ff000000",
    )

    await async_ipr.tc(
        'add-filter',
        'u32',
        index=index,
        handle=0,
        parent=0x10000,
        prio=10,
        protocol=protocols.ETH_P_IP,
        target=0x10020,
        keys=['0x5/0xf+0', '0x10/0xff+33'],
    )
    assert filter_exists(
        ifname=ifname,
        kind='u32',
        parent='1:',
        protocol='ip',
        match_value='10000000',
        match_mask='ff000000',
    )

    # complementary delete commands
    await async_ipr.tc('del-filter', index=index, handle='0:0', parent='1:0')
    assert not filter_exists(ifname=ifname, kind='u32', parent='1:0')

    await async_ipr.tc('del-class', index=index, handle='1:20', parent='1:1')
    assert not class_exists(
        ifname=ifname, kind='htb', handle='1:20', parent='1:1'
    )
    assert class_exists(ifname=ifname, kind='htb', handle='1:10', parent='1:1')
    assert class_exists(ifname=ifname, kind='htb', handle='1:1', root=True)

    await async_ipr.tc('del-class', index=index, handle='1:10', parent='1:1')
    assert not class_exists(
        ifname=ifname, kind='htb', handle='1:20', parent='1:1'
    )
    assert not class_exists(
        ifname=ifname, kind='htb', handle='1:10', parent='1:1'
    )
    assert class_exists(ifname=ifname, kind='htb', handle='1:1', root=True)

    await async_ipr.tc('del-class', index=index, handle='1:1', parent='1:0')
    assert not class_exists(
        ifname=ifname, kind='htb', handle='1:20', parent='1:1'
    )
    assert not class_exists(
        ifname=ifname, kind='htb', handle='1:10', parent='1:1'
    )
    assert not class_exists(ifname=ifname, kind='htb', handle='1:1', root=True)

    await async_ipr.tc('del', index=index, handle=root_handle, root=True)
    assert not qdisc_exists(ifname=ifname, handle=root_handle)
