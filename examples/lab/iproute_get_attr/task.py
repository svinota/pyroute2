from pyroute2 import IPRoute

ipr = IPRoute()

print('iterate network interfaces\n')
for msg in ipr.get_links():
    # using dict API
    print('interface index:', msg['index'])
    # using .get_attr()
    print('interface name:', msg.get_attr('IFLA_IFNAME'))
    # using .get()
    print('forwarding flag:', msg.get(('af_spec', 'af_inet', 'forwarding')))
    # using .get_nested()
    print('same with get_nested():',
        msg.get_nested('IFLA_AF_SPEC', 'AF_INET')['forwarding']
    )
    print('\nraw interface data\n', msg)

ipr.close()
