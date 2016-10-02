from socket import AF_UNIX
from pyroute2 import DiagSocket


class TestDiag(object):

    def test_basic(self):
        sstats_set = set()
        pstats_set = set()
        sstats = None
        fd = None

        with DiagSocket() as ds:
            ds.bind()
            sstats = ds.get_sock_stats(family=AF_UNIX)
            for s in sstats:
                sstats_set.add(s['udiag_ino'])

        with open('/proc/net/unix') as fd:
            for l in fd.readlines():
                l = l.split()
                if l[0][:2] != 'ff':
                    continue
                pstats_set.add(int(l[6]))

        assert sstats_set == pstats_set
