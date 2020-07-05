import sys
from pyroute2.ndb.cluster import init

with open(sys.argv[1]) as config:
    ndb = init(config)
