import time
from socket import AF_INET, AF_INET6

import pytest
from pr2test.context_manager import skip_if_not_supported
from pr2test.marks import require_root

pytestmark = [require_root()]


def test_real_links(context):
    links = set([x['index'] for x in context.ipr.get_links()])
    neigh = set([x['ifindex'] for x in context.ipr.get_neighbours()])
    assert neigh <= links


def test_filter(context):
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    index, ifname = context.default_interface
    lladdr = '00:11:22:33:44:55'
    # this is required -- the default interface takes time to setup
    time.sleep(0.5)
    # inject arp records
    context.ipr.neigh('add', dst=ipaddr1, lladdr=lladdr, ifindex=index)
    context.ipr.neigh('add', dst=ipaddr2, lladdr=lladdr, ifindex=index)
    # assert two arp records on the interface
    assert (
        len(tuple(context.ipr.get_neighbours(ifindex=index, family=AF_INET)))
        == 2
    )
    # filter by dst
    assert len(tuple(context.ipr.get_neighbours(dst=ipaddr1))) == 1
    # filter with lambda
    assert (
        len(
            tuple(
                context.ipr.get_neighbours(
                    match=lambda x: x['ifindex'] == index
                    and x['family'] == AF_INET
                )
            )
        )
        == 2
    )


@skip_if_not_supported
def test_get(context):
    ipaddr1 = context.new_ipaddr
    index, ifname = context.default_interface
    lladdr = '00:11:22:33:44:55'
    # this is required -- the default interface takes time to setup
    time.sleep(0.5)
    context.ipr.neigh('add', dst=ipaddr1, lladdr=lladdr, ifindex=index)
    res = context.ipr.neigh('get', dst=ipaddr1, ifindex=index)
    assert res[0].get_attr("NDA_DST") == ipaddr1


@pytest.mark.parametrize(
    'family,ipaddr_source,prefixlen',
    ((AF_INET, 'new_ipaddr', 24), (AF_INET6, 'new_ip6addr', 64)),
)
def test_dump(context, family, ipaddr_source, prefixlen):
    index, ifname = context.default_interface
    ipaddr1 = getattr(context, ipaddr_source)
    # wait for the link
    context.ipr.poll(context.ipr.link, 'dump', index=index, state='up')
    context.ipr.addr(
        'add', index=index, family=family, address=ipaddr1, prefixlen=prefixlen
    )
    # wait for the address
    context.ipr.poll(context.ipr.addr, 'dump', index=index, address=ipaddr1)
    # now add neighbours; to keep it simpler, don't take care if we loose
    # some of the neighbour records, enough to have there at least one, so
    # add some and continue
    for last_byte in range(32):
        l2addr = f'00:11:22:33:44:{last_byte:02}'
        context.ipr.neigh(
            'add',
            dst=getattr(context, ipaddr_source),
            lladdr=l2addr,
            ifindex=index,
        )
    # ok, now the dump should not be empty
    assert len(tuple(context.ipr.neigh('dump', family=family))) > 0
