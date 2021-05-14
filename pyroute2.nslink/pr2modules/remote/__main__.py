import sys
from pr2modules.remote import Server
from pr2modules.remote import Transport


Server(Transport(sys.stdin), Transport(sys.stdout))
