import json
import pickle
from pyroute2 import IPRoute


class TestSerialize(object):

    def setup(self):
        with IPRoute() as ipr:
            self.links = ipr.link('dump')
        self.names = set([x.get_attr('IFLA_IFNAME') for x in self.links])
        self.indices = set([x['index'] for x in self.links])

    def _check(self, loaded):
        names = set([x.get_attr('IFLA_IFNAME') for x in loaded])
        indices = set([x['index'] for x in loaded])
        assert names == self.names
        assert indices == self.indices

    def test_pickle(self):
        saved = pickle.dumps(self.links)
        loaded = pickle.loads(saved)
        self._check(loaded)

    def test_json(self):
        saved = json.dumps([x.dump() for x in self.links])
        msg_type = type(self.links[0])
        loaded = [msg_type().load(x) for x in json.loads(saved)]
        self._check(loaded)

    def test_dump(self):
        saved = [(type(x), x.dump()) for x in self.links]
        loaded = [x[0]().load(x[1]) for x in saved]
        self._check(loaded)
