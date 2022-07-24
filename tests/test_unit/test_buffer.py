import pytest

from pyroute2.netlink.buffer import Buffer, Page

buffer_settings = (
    'mode,size,page_size',
    (('internal', 10485760, 32768), ('shared', 10485760, 32768)),
)


@pytest.mark.parametrize(*buffer_settings)
def test_create_buffer(mode, size, page_size):
    buffer = Buffer(mode, size, page_size)
    assert buffer.mode == mode
    assert buffer.size == size
    assert buffer.page_size == page_size
    minimal_index = 0
    maximal_index = size // page_size
    assert len(buffer.directory) == maximal_index
    for index, page in buffer.directory.items():
        assert minimal_index <= index <= maximal_index
        assert isinstance(page, Page)
        assert page.offset == index * page_size
        assert page.free is True
    buffer.close()
