from pprint import pprint
from pyroute2 import taskstats

t = taskstats()
pprint(t.get_pid_stat(1))
