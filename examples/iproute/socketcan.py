'''
Simplest example to set CAN bitrate.
'''

from pyroute2 import IPRoute

with IPRoute() as ip_route:
    # loolkup can0 interface
    idx = ip_route.link_lookup(ifname='can0')[0]
    link = ip_route.link('get', index=idx)

    # bring can0 interface down. CAN settings can be set only
    # if the interface is down
    if 'state' in link[0] and link[0]['state'] == 'up':
        ip_route.link('set', index=idx, state='down')

    # set CAN birate
    ip_route.link('set', index=idx, kind='can', can_bittiming={'bitrate': 250000 })

    # bring can0 interface up
    ip_route.link('set', index=idx, state='up')
