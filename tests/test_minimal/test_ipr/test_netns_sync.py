from pyroute2.netns import getnsfd


def test_set_netnsid_fd(sync_ipr, nsname):
    fd = getnsfd(nsname)
    sync_ipr.set_netnsid(fd=fd, nsid=42)
    assert sync_ipr.get_netnsid(fd=fd)['nsid'] == 42
