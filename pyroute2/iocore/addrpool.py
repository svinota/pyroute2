import threading


class AddrPool(object):
    '''
    Address pool
    '''
    cell = 0xffffffffffffffff

    def __init__(self, minaddr=0xf, maxaddr=0xffffff):
        self.cell_size = 0  # in bits
        mx = self.cell
        while mx:
            mx >>= 8
            self.cell_size += 1
        self.cell_size *= 8
        # calculate, how many ints we need to bitmap all addresses
        cells = (maxaddr - minaddr) / self.cell_size + 1
        # generate array
        self.addr_map = [self.cell for x in range(cells)]
        self.minaddr = minaddr
        self.maxaddr = maxaddr
        self.lock = threading.Lock()

    def alloc(self):
        with self.lock:
            # iterate through addr_map
            base = 0
            for cell in self.addr_map:
                if cell:
                    # not allocated addr
                    bit = 0
                    while True:
                        if (1 << bit) & self.addr_map[base]:
                            self.addr_map[base] ^= 1 << bit
                            break
                        bit += 1
                    return (base * self.cell_size + bit) + self.minaddr
                base += 1
            raise KeyError('no free address available')

    def free(self, addr):
        with self.lock:
            addr -= self.minaddr
            base = addr / self.cell_size
            bit = addr % self.cell_size
            if self.addr_map[base] & (1 << bit):
                raise KeyError('address is not allocated')
            self.addr_map[base] ^= 1 << bit
