from socket import AF_INET

from pr2test.marks import require_root

from pyroute2 import DiagSocket

pytestmark = [require_root()]


def test_basic():
    sstats_set = set()
    pstats_set = set()
    sstats = None
    fd = None

    with DiagSocket() as ds:
        ds.bind()
        sstats = ds.get_sock_stats(family=AF_INET)
        for s in sstats:
            sstats_set.add(s['idiag_inode'])

    with open('/proc/net/tcp') as fd:
        for line in fd.readlines():
            line = line.split()
            try:
                pstats_set.add(int(line[9]))
            except ValueError:
                pass

    assert len(sstats_set - pstats_set) < 10
    assert len(pstats_set - sstats_set) < 10
