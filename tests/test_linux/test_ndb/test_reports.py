import csv
import json
from socket import AF_INET

import pytest
from pr2modules.ndb.report import Record, RecordSet
from pr2modules.ndb.objects import RTNL_Object
from pr2test.context_manager import make_test_matrix, skip_if_not_supported

from pyroute2.common import basestring

test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_types(context):
    # check for the report type here
    assert isinstance(context.ndb.interfaces.summary(), RecordSet)
    # repr must be a string
    assert isinstance(repr(context.ndb.interfaces.summary()), basestring)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_iter_keys(context):
    for name in ('interfaces', 'addresses', 'neighbours', 'routes', 'rules'):
        view = getattr(context.ndb, name)
        for key in view:
            assert isinstance(key, Record)
            obj = view.get(key)
            if obj is not None:
                assert isinstance(obj, RTNL_Object)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_join(context):

    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr1, prefixlen=24)
        .add_ip(address=ipaddr2, prefixlen=24)
        .commit()
    )

    addr = (
        context.ndb.addresses.dump()
        .filter(lambda x: x.family == AF_INET)
        .join(
            (context.ndb.interfaces.dump().filter(lambda x: x.state == 'up')),
            condition=lambda l, r: l.index == r.index and r.ifname == ifname,
            prefix='if_',
        )
        .select('address')
    )

    s1 = set((ipaddr1, ipaddr2))
    s2 = set([x.address for x in addr])
    assert s1 == s2


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_slices(context):
    a = list(context.ndb.rules.dump())
    ln = len(a) - 1
    # simple indices
    assert a[0] == context.ndb.rules.dump()[0]
    assert a[1] == context.ndb.rules.dump()[1]
    assert a[-1] == context.ndb.rules.dump()[-1]
    assert context.ndb.rules.dump()[ln] == a[-1]
    try:
        context.ndb.rules.dump()[len(a)]
    except IndexError:
        pass
    # slices
    assert a[0:] == context.ndb.rules.dump()[0:]
    assert a[:3] == context.ndb.rules.dump()[:3]
    assert a[0:3] == context.ndb.rules.dump()[0:3]
    assert a[1:3] == context.ndb.rules.dump()[1:3]
    # negative slices
    assert a[-3:] == context.ndb.rules.dump()[-3:]
    assert a[-3:-1] == context.ndb.rules.dump()[-3:-1]
    # mixed
    assert a[-ln : ln - 1] == context.ndb.rules.dump()[-ln : ln - 1]
    # step
    assert a[2:ln:2] == context.ndb.rules.dump()[2:ln:2]


@pytest.mark.parametrize('context', test_matrix, indirect=True)
@skip_if_not_supported
def test_report_chains(context):
    ipnet = str(context.ipnets[1].network)
    ipaddr = context.new_ipaddr
    router = context.new_ipaddr
    ifname = context.new_ifname

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr, prefixlen=24)
        .commit()
    )

    (
        context.ndb.routes.create(
            dst=ipnet,
            dst_len=24,
            gateway=router,
            encap={'type': 'mpls', 'labels': [20, 30]},
        ).commit()
    )

    encap = tuple(
        context.ndb.routes.dump()
        .filter(oif=context.ndb.interfaces[ifname]['index'])
        .filter(lambda x: x.encap is not None)
        .select('encap')
        .transform(encap=lambda x: json.loads(x))
    )[0].encap

    assert isinstance(encap, list)
    assert encap[0]['label'] == 20
    assert encap[0]['bos'] == 0
    assert encap[1]['label'] == 30
    assert encap[1]['bos'] == 1


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_json(context):
    data = json.loads(''.join(context.ndb.interfaces.summary().format('json')))
    assert isinstance(data, list)
    for row in data:
        assert isinstance(row, dict)


class MD(csv.Dialect):
    quotechar = "'"
    doublequote = False
    quoting = csv.QUOTE_MINIMAL
    delimiter = ","
    lineterminator = "\n"


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_csv(context):
    record_length = 0

    for record in context.ndb.routes.dump():
        if record_length == 0:
            record_length = len(record)
        else:
            assert len(record) == record_length

    reader = csv.reader(context.ndb.routes.dump().format('csv'), dialect=MD())
    for record in reader:
        assert len(record) == record_length


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_nested_ipaddr(context):
    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(address=ipaddr1, prefixlen=24)
        .add_ip(address=ipaddr2, prefixlen=24)
        .commit()
    )

    records = repr(
        context.ndb.interfaces[ifname]
        .ipaddr.dump()
        .filter(lambda x: x.family == AF_INET)
    )
    rlen = len(records.split('\n'))
    # 2 ipaddr
    assert rlen == 2


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_nested_ports(context):
    ifbr0 = context.new_ifname
    ifbr0p0 = context.new_ifname
    ifbr0p1 = context.new_ifname

    with context.ndb.interfaces as i:
        i.create(ifname=ifbr0p0, kind='dummy').commit()
        i.create(ifname=ifbr0p1, kind='dummy').commit()
        (
            i.create(ifname=ifbr0, kind='bridge')
            .add_port(ifbr0p0)
            .add_port(ifbr0p1)
            .commit()
        )

    records = len(
        repr(context.ndb.interfaces[ifbr0].ports.summary()).split('\n')
    )
    # 1 port
    assert records == 2
