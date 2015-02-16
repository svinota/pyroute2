###
#
# This example shows how to define and use a custom socket base
# class to be used with NetlinkSocket.
#
# socket_wrapper module overrides the SocketBase; only after
# that we should import IPRoute
#
# Override SocketBase
import socket_wrapper
# Import and run IPRoute
from pyroute2.iproute import IPRoute
# make PEP8 happy
__all__ = ["socket_wrapper", "IPRoute"]

ip = IPRoute()
print(ip.get_addr())
ip.close()
