from pr2test.context_manager import skip_if_not_supported

from pyroute2 import IPRoute, RemoteIPRoute


@skip_if_not_supported
def test_links():
    with IPRoute() as ipr:
        links1 = set([x.get_attr('IFLA_IFNAME') for x in ipr.get_links()])

    with RemoteIPRoute() as ipr:
        links2 = set([x.get_attr('IFLA_IFNAME') for x in ipr.get_links()])

    assert links1 == links2
