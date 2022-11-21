Access netlink message attributes.

* `get_links()` returns an iterator over link objects
* `msg.get('index')` returns `index` field just like `msg['index']` does
* `msg.get('ifname')` returns `IFLA_IFNAME` value as a string
* `msg.get('af_spec')` returns `IFLA_AF_SPEC` as a dict
* `msg.get(('af_spec', 'af_inet', 'forwarding'))` as an int
