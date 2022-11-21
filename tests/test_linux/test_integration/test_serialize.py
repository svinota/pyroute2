import json
import pickle


def _check(context, loaded):
    names = set([x.get_attr('IFLA_IFNAME') for x in loaded])
    indices = set([x['index'] for x in loaded])
    assert names == {x.ifname for x in context.ndb.interfaces.dump()}
    assert indices == {x.index for x in context.ndb.interfaces.dump()}


def test_pickle(context):
    links = tuple(context.ipr.link('dump'))
    saved = pickle.dumps(links)
    loaded = pickle.loads(saved)
    _check(context, loaded)


def test_json(context):
    links = tuple(context.ipr.link('dump'))
    saved = json.dumps([x.dump() for x in links])
    msg_type = type(links[0])
    loaded = [msg_type().load(x) for x in json.loads(saved)]
    _check(context, loaded)


def test_dump(context):
    links = tuple(context.ipr.link('dump'))
    saved = [(type(x), x.dump()) for x in links]
    loaded = [x[0]().load(x[1]) for x in saved]
    _check(context, loaded)
