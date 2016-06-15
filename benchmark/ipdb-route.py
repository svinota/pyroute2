import logging
from pyroute2 import IPDB
logging.basicConfig()


def main():
    with IPDB() as ip:
        try:
            # create static routes
            for i in range(2, 10):
                for k in range(2, 254):
                    ip.routes.add({'dst': '10.%i.%i.0/24' % (i, k),
                                   'gateway': '127.0.0.2'}).commit()

        finally:
            # remove static routes
            for i in range(2, 10):
                for k in range(2, 254):
                    if '10.%i.%i.0/24' % (i, k) in ip.routes:
                        with ip.routes['10.%i.%i.0/24' % (i, k)] as t:
                            t.remove()

main()
