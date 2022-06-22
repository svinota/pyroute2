from pr2test.marks import require_root

pytestmark = [require_root()]


def callback(msg, cb_context):
    cb_context['counter'] += 1


def test_callbacks_positive(context):
    ifname = context.new_ifname
    cb_context = {'counter': 0}
    interface = context.ndb.interfaces.create(
        ifname=ifname, kind='dummy'
    ).commit()

    context.ipr.register_callback(
        callback,
        lambda x: x.get('index', None) == interface['index'],
        (cb_context,),
    )
    context.ipr.link('set', index=interface['index'], state='up')
    context.ipr.link('get', index=interface['index'])
    counter = cb_context['counter']
    assert counter > 0
    context.ipr.unregister_callback(callback)
    context.ipr.link('set', index=interface['index'], state='down')
    context.ipr.link('get', index=interface['index'])
    assert cb_context['counter'] == counter


def test_callbacks_negative(context):
    ifname = context.new_ifname
    cb_context = {'counter': 0}
    interface = context.ndb.interfaces.create(
        ifname=ifname, kind='dummy'
    ).commit()

    context.ipr.register_callback(
        callback, lambda x: x.get('index', None) == -1, (cb_context,)
    )
    context.ipr.link('set', index=interface['index'], state='up')
    context.ipr.link('get', index=interface['index'])
    counter = cb_context['counter']
    assert counter == 0
