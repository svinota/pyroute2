from pr2test.marks import require_root

pytestmark = [require_root()]


def test_nla_operators(context):
    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    interface = (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(f'{ipaddr1}/24')
        .add_ip(f'{ipaddr2}/24')
        .commit()
    )

    r = context.ipr.addr('dump', index=interface['index'])
    complement = r[0] - r[1]
    intersection = r[0] & r[1]

    assert complement.get_attr('IFA_ADDRESS') == ipaddr1
    assert complement.get_attr('IFA_LABEL') is None
    assert complement['prefixlen'] == 0
    assert complement['index'] == 0

    assert intersection.get_attr('IFA_ADDRESS') is None
    assert intersection.get_attr('IFA_LABEL') == ifname
    assert intersection['prefixlen'] == 24
    assert intersection['index'] == context.ndb.interfaces[ifname]['index']


def test_nla_compare(context):
    lvalue = context.ipr.get_links()
    rvalue = context.ipr.get_links()
    assert lvalue is not rvalue
    if lvalue == rvalue:
        pass
    if lvalue != rvalue:
        pass
    assert lvalue != 42
