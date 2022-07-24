from multiprocessing import shared_memory


class Page:
    '''
    Memory page.
    '''

    def __init__(self, buffer, offset):
        self.buffer = buffer
        self.offset = offset
        self.free = True

    def close(self):
        self.buffer.release()


class Buffer:
    '''
    Manage the buffer memory to receive raw netlink data.
    '''

    def __init__(self, mode='internal', size=10485760, page_size=32768):
        self.mode = mode
        self.size = size
        self.page_size = page_size
        if self.mode == 'internal':
            self.mem = None
            self.buf = bytearray(self.size)
        elif self.mode == 'shared':
            self.mem = shared_memory.SharedMemory(create=True, size=self.size)
            self.buf = self.mem.buf
        self.view = memoryview(self.buf)
        self.directory = {}
        for index in range(size // page_size):
            offset = index * page_size
            self.directory[index] = Page(
                self.view[offset : offset + self.page_size], offset
            )

    def get_free_page(self):
        for index, page in self.directory.items():
            if page.free:
                return page
        raise KeyError('no free memory pages available')

    def close(self):
        for page in self.directory.values():
            page.close()
        self.view.release()
        if self.mode == 'shared':
            self.mem.close()
            self.mem.unlink()

    def __getitem__(self, key):
        return self.directory[key]
