from pyroute2.common import hexdump
from pyroute2 import IPQSocket
from pyroute2.netlink.ipq import NF_ACCEPT
from dpkt.ip import IP

ip = IPQSocket()
ip.bind()
try:
    while True:
        msg = ip.get()[0]
        print("\n")
        print(hexdump(msg.raw))
        print(repr(IP(msg['payload'])))
        ip.verdict(msg['packet_id'], NF_ACCEPT)
except:
    pass
finally:
    ip.release()
