from pyroute2 import DiagSocket


class TestDiag(object):

    def test_basic(self):
        with DiagSocket() as ds:
            ds.bind()
            assert len(ds.test()) > 0
