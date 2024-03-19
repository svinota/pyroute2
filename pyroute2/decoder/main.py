'''
A cli tool to decode netlink buffers.
'''

from args import args
from loader import get_loader


def run():
    loader = get_loader(args)
    for message in loader.data:
        print(message)


if __name__ == "__main__":
    run()
