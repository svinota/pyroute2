def records(ndb, query):
    return len(list(ndb.db.fetch(query)))


def test_snapshot_repeat(ndb, test_link):
    # Bug-Url: https://github.com/svinota/pyroute2/issues/1364
    x = test_link.index
    with ndb.interfaces[test_link.ifname] as i:
        i.del_ip()
    ctxid = i.asyncore.last_save.ctxid
    assert records(ndb, f'select * from addresses_{ctxid}') == 1
    assert records(ndb, 'select * from addresses where f_index = 1') >= 1
    assert records(ndb, f'select * from addresses where f_index = {x}') == 0
    with ndb.interfaces[test_link.ifname] as i:
        i.del_ip()
    assert records(ndb, f'select * from addresses_{ctxid}') == 0
    assert records(ndb, 'select * from addresses where f_index = 1') >= 1
    assert records(ndb, f'select * from addresses where f_index = {x}') == 0
