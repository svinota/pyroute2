'''
'''
import struct
import threading
from socket import inet_pton
from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import basestring


class LinkedSet(set):
    '''
    Utility class, used by `Interface` to track ip addresses
    and ports. Called "linked" as it automatically updates all
    instances, linked with it.

    Target filter is a function, that returns `True` if a set
    member should be counted in target checks (target methods
    see below), or `False` if it should be ignored.
    '''
    def target_filter(self, x):
        return True

    def __init__(self, *argv, **kwarg):
        set.__init__(self, *argv, **kwarg)

        def _check_default_target(self):
            if self._ct is not None:
                if set(filter(self.target_filter, self)) == \
                        set(filter(self.target_filter, self._ct)):
                    self._ct = None
                    return True
            return False
        self.lock = threading.RLock()
        self.target = threading.Event()
        self.targets = {self.target: _check_default_target}
        self._ct = None
        self.raw = {}
        self.links = []
        self.exclusive = set()

    def __getitem__(self, key):
        return self.raw[key]

    def clear_target(self, target=None):
        with self.lock:
            if target is None:
                self._ct = None
                self.target.clear()
            else:
                target.clear()
                del self.targets[target]

    def set_target(self, value, ignore_state=False):
        '''
        Set target state for the object and clear the target
        event. Once the target is reached, the event will be
        set, see also: `check_target()`

        Args:
            - value (set): the target state to compare with
        '''
        with self.lock:
            if isinstance(value, (set, tuple, list)):
                self._ct = set(value)
                self.target.clear()
                # immediately check, if the target already
                # reached -- otherwise you will miss the
                # target forever
                if not ignore_state:
                    self.check_target()
            elif hasattr(value, '__call__'):
                new_target = threading.Event()
                self.targets[new_target] = value
                if not ignore_state:
                    self.check_target()
                return new_target
            else:
                raise TypeError("target type not supported")

    def check_target(self):
        '''
        Check the target state and set the target event in the
        case the state is reached. Called from mutators, `add()`
        and `remove()`
        '''
        with self.lock:
            for evt in self.targets:
                if self.targets[evt](self):
                    evt.set()

    def add(self, key, raw=None, cascade=False):
        '''
        Add an item to the set and all connected instances,
        check the target state.

        Args:
            - key: any hashable object
            - raw (optional): raw representation of the object

        Raw representation is not required. It can be used, e.g.,
        to store RTM_NEWADDR RTNL messages along with
        human-readable ip addr representation.
        '''
        with self.lock:
            if cascade and (key in self.exclusive):
                return
            if key not in self:
                self.raw[key] = raw
                super(LinkedSet, self).add(key)
                for link in self.links:
                    link.add(key, raw, cascade=True)
            self.check_target()

    def remove(self, key, raw=None, cascade=False):
        '''
        Remove an item from the set and all connected instances,
        check the target state.
        '''
        with self.lock:
            if cascade and (key in self.exclusive):
                return
            super(LinkedSet, self).remove(key)
            self.raw.pop(key, None)
            for link in self.links:
                if key in link:
                    link.remove(key, cascade=True)
            self.check_target()

    def unlink(self, key):
        '''
        Exclude key from cascade updates.
        '''
        self.exclusive.add(key)

    def relink(self, key):
        '''
        Do not ignore key on cascade updates.
        '''
        self.exclusive.remove(key)

    def connect(self, link):
        '''
        Connect a LinkedSet instance to this one. Connected
        sets will be updated together with this instance.
        '''
        if not isinstance(link, LinkedSet):
            raise TypeError()
        self.links.append(link)

    def disconnect(self, link):
        self.links.remove(link)

    def __repr__(self):
        return repr(list(self))


class IPaddrSet(LinkedSet):
    '''
    LinkedSet child class with different target filter. The
    filter ignores link local IPv6 addresses when sets and checks
    the target.

    The `wait_ip()` routine by default does not ignore link local
    IPv6 addresses, but it may be changed with the `ignore_link_local`
    argument.
    '''
    def wait_ip(self, net, mask=None, timeout=None, ignore_link_local=False):
        family = AF_INET6 if net.find(':') >= 0 else AF_INET
        alen = 32 if family == AF_INET else 128
        net = inet_pton(family, net)
        if mask is None:
            mask = alen
        if family == AF_INET:
            net = struct.unpack('>I', net)[0]
        else:
            na, nb = struct.unpack('>QQ', net)
            net = (na << 64) | nb
        match = net & (((1 << mask) - 1) << (alen - mask))

        def match_ip(ipset):
            for rnet, rmask in ipset:
                rfamily = AF_INET6 if rnet.find(':') >= 0 else AF_INET
                if family != rfamily:
                    continue
                if family == AF_INET6 and \
                        ignore_link_local and \
                        rnet[:4] == 'fe80' and \
                        rmask == 64:
                    continue
                rnet = inet_pton(family, rnet)
                if family == AF_INET:
                    rnet = struct.unpack('>I', rnet)[0]
                else:
                    rna, rnb = struct.unpack('>QQ', rnet)
                    rnet = (rna << 64) | rnb
                if (rnet & (((1 << mask) - 1) << (alen - mask))) == match:
                    return True
            return False
        target = self.set_target(match_ip)
        target.wait(timeout)
        ret = target.is_set()
        self.clear_target(target)
        return ret

    def target_filter(self, x):
        return not ((x[0][:4] == 'fe80') and (x[1] == 64))

    def __repr__(self):
        return repr(['%s/%s' % x for x in self])

    def __getitem__(self, key):
        if isinstance(key, (tuple, list)):
            return self.raw[key]
        elif isinstance(key, int):
            return self.raw[tuple(self.raw.keys())[key]]
        elif isinstance(key, basestring):
            key = key.split('/')
            key = (key[0], int(key[1]))
            return self.raw[key]
        else:
            TypeError('wrong key type')
