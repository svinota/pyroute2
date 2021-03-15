from pr2test.tools import interface_exists


def test_context_manager(local_ctx):

    ifname = local_ctx.ifname
    address = '00:11:22:36:47:58'
    spec = local_ctx.getspec(ifname=ifname, kind='dummy')
    ndb = local_ctx.ndb

    ifobj = ndb.interfaces.create(**spec)

    with ifobj:
        pass

    assert interface_exists(ifname, state='down')

    with ifobj:
        ifobj['state'] = 'up'
        ifobj['address'] = address

    spec = local_ctx.getspec(ifname=ifname)

    assert interface_exists(ifname, address=address, state='up')

    with ifobj:
        ifobj.remove()

    assert not interface_exists(ifname)
