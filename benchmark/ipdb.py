import logging
from pyroute2 import IPDB
logging.basicConfig()


def main(ifnum):
    with IPDB() as ip:
        for i in range(ifnum):
            try:
                # create ports
                for k in range(30):
                    with ip.create(kind='dummy',
                                   ifname='test-%ip%i' % (i, k)) as t:
                        t.up()
                # create bridge, bring it up and add ports
                with ip.create(kind='bridge', ifname='test-%i' % i) as t:
                    for k in range(30):
                        t.add_port(ip.interfaces['test-%ip%i' % (i,
                                                                 k)]['index'])
                    t.up()
                # add a network one ip by one
                for k in range(2, 254):
                    with ip.interfaces['test-%i' % i] as t:
                        t.add_ip('172.16.%i.%i/24' % (i, k))
                # add a network at once (compare in line-profiler)
                with ip.interfaces['test-%i' % i] as t:
                    for k in range(2, 254):
                        t.add_ip('172.16.%i.%i/24' % (i + ifnum + 1, k))
            except:
                pass

        for i in range(ifnum):
            try:
                for k in range(30):
                    if 'test-%ip%i' % (i, k) in ip.interfaces:
                        ip.interfaces['test-%ip%i' % (i, k)].remove().commit()
                if 'test-%i' % i in ip.interfaces:
                    ip.interfaces['test-%i' % i].remove().commit()
            except:
                pass

main(1)
