import time
from socket import AF_INET

from pr2test.context_manager import skip_if_not_supported


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
    assert len(context.ipr.get_neighbours(ifindex=index, family=AF_INET)) == 2
    # filter by dst
    assert len(context.ipr.get_neighbours(dst=ipaddr1)) == 1
    # filter with lambda
    assert (
        len(
            context.ipr.get_neighbours(
                match=lambda x: x['ifindex'] == index
                and x['family'] == AF_INET
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
