from pr2test.marks import require_root

pytestmark = [require_root()]


def test_nlmsg_operators(context):
    ifname = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr
    interface = (
        context.ndb.interfaces.create(ifname=ifname, kind='dummy', state='up')
        .add_ip(f'{ipaddr1}/24')
        .add_ip(f'{ipaddr2}/24')
        .commit()
    )

    r = tuple(context.ipr.addr('dump', index=interface['index']))
    complement = r[0] - r[1]
    intersection = r[0] & r[1]

    assert complement.get_attr('IFA_ADDRESS') == ipaddr1
    assert complement.get_attr('IFA_LABEL') is None
    assert 'prefixlen' not in complement
    assert 'index' not in complement

    assert intersection.get_attr('IFA_ADDRESS') is None
    assert intersection.get_attr('IFA_LABEL') == ifname
    assert intersection['prefixlen'] == 24
    assert intersection['index'] == context.ndb.interfaces[ifname]['index']


def test_nlmsg_compare_equal(context):
    lvalue = tuple(context.ipr.get_links())[0]
    rvalue = tuple(context.ipr.get_links())[0]
    assert lvalue is not rvalue
    assert lvalue == rvalue


def test_nlmsg_compare_not_equal(context):
    lvalue = tuple(context.ipr.get_links())[0]
    rvalue = tuple(context.ipr.get_links())[1]
    assert lvalue is not rvalue
    assert lvalue != rvalue


def test_nlmsg_compare_int(context):
    lvalue = tuple(context.ipr.get_links())[0]
    rvalue = 42
    assert lvalue is not rvalue
    assert lvalue != rvalue
