import pytest

from pyroute2.netlink.buffer import Buffer, Page

buffer_settings = (
    'mode,size,page_size',
    (('internal', 10485760, 32768), ('shared', 10485760, 32768)),
)


@pytest.mark.parametrize(*buffer_settings)
def test_create_buffer(mode, size, page_size):
    try:
        buffer = Buffer(mode, size, page_size)
    except ModuleNotFoundError:
        pytest.skip(f'buffer mode "{mode}" not supported')
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
        assert page.is_free is True
    buffer.close()


@pytest.mark.parametrize(*buffer_settings)
def test_use_all_pages(mode, size, page_size):
    try:
        buffer = Buffer(mode, size, page_size)
    except ModuleNotFoundError:
        pytest.skip(f'buffer mode "{mode}" not supported')
    maximal_index = size // page_size
    marker = 0x05
    for _ in range(maximal_index):
        page = buffer.get_free_page()
        assert not page.is_free
        page.view[0] = marker
        assert page.view[0] == marker
        assert buffer.view[page.offset] == marker
        assert buffer.buf[page.offset] == marker
        marker += 1
        if marker == 0xFF:
            marker = 0x05

    with pytest.raises(MemoryError):
        buffer.get_free_page()
    buffer.close()


@pytest.mark.parametrize(*buffer_settings)
def test_context_manager(mode, size, page_size):
    try:
        with Buffer(mode, size, page_size) as buffer:
            assert buffer.mode == mode
    except ModuleNotFoundError:
        pytest.skip(f'buffer mode "{mode}" not supported')
