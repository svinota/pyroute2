import threading


class AddrPool(object):
    '''
    Address pool
    '''
    cell = 0xffffffffffffffff

    def __init__(self, minaddr=0xf, maxaddr=0xffffff, reverse=False):
        self.cell_size = 0  # in bits
        mx = self.cell
        self.reverse = reverse
        while mx:
            mx >>= 8
            self.cell_size += 1
        self.cell_size *= 8
        # calculate, how many ints we need to bitmap all addresses
        self.cells = int((maxaddr - minaddr) / self.cell_size + 1)
        # initial array
        self.addr_map = [self.cell]
        self.minaddr = minaddr
        self.maxaddr = maxaddr
        self.lock = threading.RLock()

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
                    ret = (base * self.cell_size + bit)

                    if self.reverse:
                        ret = self.maxaddr - ret
                    else:
                        ret = ret + self.minaddr

                    if self.minaddr <= ret <= self.maxaddr:
                        return ret
                    else:
                        self.free(ret)
                        raise KeyError('no free address available')

                base += 1
            # no free address available
            if len(self.addr_map) < self.cells:
                # create new cell to allocate address from
                self.addr_map.append(self.cell)
                return self.alloc()
            else:
                raise KeyError('no free address available')

    def free(self, addr):
        with self.lock:
            if self.reverse:
                addr = self.maxaddr - addr
            else:
                addr -= self.minaddr
            base = addr // self.cell_size
            bit = addr % self.cell_size
            if len(self.addr_map) <= base:
                raise KeyError('address is not allocated')
            if self.addr_map[base] & (1 << bit):
                raise KeyError('address is not allocated')
            self.addr_map[base] ^= 1 << bit
