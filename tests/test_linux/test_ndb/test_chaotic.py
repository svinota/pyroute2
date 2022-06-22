from pr2test.marks import require_root
from pr2test.tools import address_exists

from pyroute2 import NDB

pytestmark = [require_root()]


def test_add_del_ip_dict(context):
    ifname = context.new_ifname
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    log_spec = (
        context.spec.log_spec[0] + '.chaotic',
        context.spec.log_spec[1],
    )

    with NDB(
        log=log_spec,
        sources=[
            {
                'target': 'localhost',
                'kind': 'ChaoticIPRoute',
                'success_rate': 0.98,
            }
        ],
    ) as test_ndb:

        (
            test_ndb.interfaces.create(
                ifname=ifname, kind='dummy', state='down'
            )
            .add_ip({'address': ifaddr1, 'prefixlen': 24})
            .add_ip({'address': ifaddr2, 'prefixlen': 24})
            .commit()
        )

        assert address_exists(context.netns, ifname=ifname, address=ifaddr1)
        assert address_exists(context.netns, ifname=ifname, address=ifaddr2)

        (
            test_ndb.interfaces[{'ifname': ifname}]
            .del_ip({'address': ifaddr2, 'prefixlen': 24})
            .del_ip({'address': ifaddr1, 'prefixlen': 24})
            .commit()
        )

        assert not address_exists(
            context.netns, ifname=ifname, address=ifaddr1
        )
        assert not address_exists(
            context.netns, ifname=ifname, address=ifaddr2
        )
