from pyroute2.common import hexdump
from pyroute2.netlink.ipq import IPQ
from pyroute2.netlink.ipq import NF_ACCEPT

ip = IPQ()
ip.monitor()
try:
    while True:
        msg = ip.get()[0]
        print(hexdump(msg.raw))
        print(msg)
        ip.verdict(msg['packet_id'], NF_ACCEPT)
except:
    pass
finally:
    ip.release()
