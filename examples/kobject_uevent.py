from pprint import pprint
from pyroute2 import UeventSocket

kus = UeventSocket()
kus.bind()
while True:
    pprint(kus.get())
