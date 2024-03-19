'''
A cli tool to decode netlink buffers.
'''

import json

from pyroute2.decoder.args import args
from pyroute2.decoder.loader import get_loader


def run():
    loader = get_loader(args)
    ret = []
    for message in loader.data:
        ret.append(message.dump())
    print(json.dumps(ret, indent=4))


if __name__ == "__main__":
    run()
