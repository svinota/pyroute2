import socket


def test_flush_rules(context):
    ifaddr1 = context.new_ipaddr
    ifaddr2 = context.new_ipaddr
    init = len(context.ipr.get_rules(family=socket.AF_INET))
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 0
    context.ipr.rule('add', table=10, priority=110)
    context.ipr.rule('add', table=15, priority=150, action='FR_ACT_PROHIBIT')
    context.ipr.rule('add', table=20, priority=200, src=ifaddr1)
    context.ipr.rule('add', table=25, priority=250, dst=ifaddr2)
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 4
    assert len(context.ipr.get_rules(src=ifaddr1)) == 1
    assert len(context.ipr.get_rules(dst=ifaddr2)) == 1
    context.ipr.flush_rules(
        family=socket.AF_INET, priority=lambda x: 100 < x < 500
    )
    assert len(context.ipr.get_rules(priority=lambda x: 100 < x < 500)) == 0
    assert len(context.ipr.get_rules(src=ifaddr1)) == 0
    assert len(context.ipr.get_rules(dst=ifaddr2)) == 0
    assert len(context.ipr.get_rules(family=socket.AF_INET)) == init
