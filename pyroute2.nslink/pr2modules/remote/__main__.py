import sys

from pr2modules.remote import Server, Transport

Server(Transport(sys.stdin), Transport(sys.stdout))
