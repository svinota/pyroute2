from pyroute2 import NetNS


def test_get_netns_info(context):
    nsname = context.new_nsname
    peer_name = context.new_ifname
    host_name = context.new_ifname
    with NetNS(nsname):
        (
            context.ndb.interfaces.create(
                ifname=host_name,
                kind='veth',
                peer={'ifname': peer_name, 'net_ns_fd': nsname},
            ).commit()
        )
        # get veth
        veth = context.ipr.link('get', ifname=host_name)[0]
        target = veth.get_attr('IFLA_LINK_NETNSID')
        for info in context.ipr.get_netns_info():
            path = info.get_attr('NSINFO_PATH')
            assert path.endswith(nsname)
            netnsid = info['netnsid']
            if target == netnsid:
                break
        else:
            raise KeyError('peer netns not found')
