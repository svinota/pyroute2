import asyncio

import pytest
from fixtures.pcap_files import PcapFile

from pyroute2.dhcp.dhcp4socket import AsyncDHCP4Socket
from pyroute2.dhcp.messages import SentDHCPMessage


class MockDHCPServerFixture:
    '''A fixture that's used to avoid a real dhcp server in unit tests.

    By replacing `AsyncDHCP4Socket.loop` with an instance of this class,
    it will wait for messages sent by `AsyncDHCPClient` and answer
    with data from `responses`, in order.

    The requests made by the client will be stored in `decoded_requests`.
    '''

    def __init__(self, responses: list[bytes]):
        self.responses: list[bytes] = responses
        self.requests: list[bytes] = []
        self.decoded_requests: list[SentDHCPMessage] = []
        # save the event_loop fixture, 'cause pytest-asyncio on Python < 3.10
        # drops the loop in the middle of the test
        self.loop = asyncio.new_event_loop()
        self._request_received = asyncio.Event()
        self.truncate_at: int = 0

    async def sock_sendall(self, sock, data: bytes):
        self.requests.append(data)
        self.decoded_requests.append(AsyncDHCP4Socket._decode_msg(data))
        self._request_received.set()

    async def sock_recv(self, sock, size: int) -> bytes:
        # wait for a request to be received to send a response
        await self._request_received.wait()
        self._request_received.clear()
        if self.responses:
            data = self.responses.pop(0)
            if self.truncate_at:
                return data[: self.truncate_at]
            return data
        # make the client timeout, the server is supposed to answer nothing
        await asyncio.sleep(9999)


@pytest.fixture
def mock_dhcp_server(
    pcap: PcapFile, monkeypatch: pytest.MonkeyPatch
) -> MockDHCPServerFixture:
    '''Monkey patches the client to respond to requests with pcap data.

    The `pcap` fixture is used which means the pcap file must be named
    after the test.
    '''
    responder = MockDHCPServerFixture(responses=pcap)
    monkeypatch.setattr(
        'pyroute2.dhcp.dhcp4socket.AsyncDHCP4Socket.loop', responder
    )
    return responder
