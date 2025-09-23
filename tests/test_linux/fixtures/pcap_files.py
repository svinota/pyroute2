from collections import UserList
from io import BufferedReader
from pathlib import Path
from struct import Struct
from typing import Iterator, NamedTuple

import pytest

FILE_HEADER_FORMAT = Struct('IHHiIII')
PKT_HEADER_FORMAT = Struct('IIII')


class PcapFileHeader(NamedTuple):
    '''The header in front of pcap files.'''

    magic_number: int
    version_major: int
    version_minor: int
    thiszone: int
    sigfigs: int
    snaplen: int
    network: int


class PcapPacketHeader(NamedTuple):
    '''The header in front of each packet in a pcap.'''

    ts_sec: int
    ts_usec: int
    incl_len: int
    orig_len: int


class PcapFile(UserList):
    '''Reads & stores raw packets from a pcap file.'''

    def __init__(self, filename: Path):
        self.filename = filename
        with self.filename.open('rb') as fp:
            super().__init__(self._parse_pcap(fp))

    @classmethod
    def _parse_pcap(cls, fp: BufferedReader) -> Iterator[bytes]:
        '''Read & yield the raw data for every packet in `fp`.'''
        header_data = fp.read(FILE_HEADER_FORMAT.size)
        cls._validate_file_header(header_data)
        pkt_hdr_size = PKT_HEADER_FORMAT.size
        while next_header := fp.read(pkt_hdr_size):
            pkt_size = cls._parse_pkt_header(next_header)
            pkt_data = fp.read(pkt_size)
            assert len(pkt_data) == pkt_size, 'truncated packet'
            yield pkt_data

    @classmethod
    def _validate_file_header(cls, data: bytes):
        '''Parse & check the pcap file header.'''
        header = PcapFileHeader(*FILE_HEADER_FORMAT.unpack(data))
        # only support v2.4 big endian pcaps, this is a test fixture after all
        assert header.magic_number == 0xA1B2C3D4
        assert (header.version_major, header.version_minor) == (2, 4)
        assert header.network == 1  # ethernet

    @classmethod
    def _parse_pkt_header(cls, data: bytes) -> int:
        '''Read the pcap header for a single packet and return its length.'''
        header = PcapPacketHeader(*PKT_HEADER_FORMAT.unpack(data))
        assert header.incl_len == header.orig_len
        return header.incl_len


@pytest.fixture
def pcap(request: pytest.FixtureRequest) -> PcapFile:
    '''Fixture that loads a pcap file named after the test.'''
    pcap_path = request.path.parent.joinpath(
        'captures',
        request.path.stem,  # test file name without the extension
        request.node.originalname,  # name of the test
    ).with_suffix('.pcap')
    return PcapFile(pcap_path)
