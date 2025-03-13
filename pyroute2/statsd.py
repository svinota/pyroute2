import ctypes
import os
import socket
from typing import Literal, Optional, Union

from pyroute2 import netns
from pyroute2.netlink.core import CoreConfig, CoreSocketSpec

metric_type = Literal['c', 'g', 'ms']


class StatsDSocket(socket.socket):
    '''StatsD client.'''

    def __init__(
        self,
        address: Optional[tuple[str, int]] = None,
        use_socket: Optional[socket.socket] = None,
        flags: int = os.O_CREAT,
        libc: Optional[ctypes.CDLL] = None,
    ):
        self.spec = CoreSocketSpec(
            CoreConfig(
                netns=None, address=address, use_socket=use_socket is not None
            )
        )
        self.status = self.spec.status
        if use_socket is not None:
            fd = use_socket.fileno()
        else:
            prime = netns.create_socket(
                self.spec['netns'], socket.AF_INET, socket.SOCK_DGRAM
            )
            fd = os.dup(prime.fileno())
            prime.close()
        super().__init__(fileno=fd)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def put(
        self, name: str, value: Union[int, str], kind: metric_type
    ) -> None:
        self.sendto(f'{name}:{value}|{kind}'.encode(), self.spec['address'])

    def incr(self, name: str, value: int = 1) -> None:
        self.put(name, value, 'c')

    def gauge(self, name: str, value: int) -> None:
        self.put(name, value, 'g')

    def timing(self, name: str, value: int) -> None:
        self.put(name, value, 'ms')
