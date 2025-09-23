from net_tools import interface_exists


def test_link_dump(sync_ipr):
    for link in sync_ipr.link('dump'):
        assert link.get('index') > 0
        assert 1 < len(link.get('ifname')) < 16


def test_link_add(sync_ipr, tmp_link_ifname, nsname):
    sync_ipr.link('add', ifname=tmp_link_ifname, kind='dummy', state='up')
    assert interface_exists(tmp_link_ifname, netns=nsname)


def test_link_get(sync_ipr, test_link_ifname):
    (link,) = sync_ipr.link('get', ifname=test_link_ifname)
    assert link.get('state') == 'up'
    assert link.get('index') > 1
    assert link.get('ifname') == test_link_ifname
    assert link.get(('linkinfo', 'kind')) == 'dummy'


def test_link_del_by_index(
    sync_ipr, test_link_ifname, test_link_index, nsname
):
    (link,) = sync_ipr.link('get', ifname=test_link_ifname)
    sync_ipr.link('del', index=test_link_index)
    assert not interface_exists(test_link_ifname, netns=nsname)


def test_link_del_by_name(sync_ipr, test_link_ifname, nsname):
    sync_ipr.link('del', ifname=test_link_ifname)
    assert not interface_exists(test_link_ifname, netns=nsname)
