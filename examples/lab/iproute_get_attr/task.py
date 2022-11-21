from pyroute2 import IPRoute

ipr = IPRoute()

print('iterate network interfaces\n')
for msg in ipr.get_links():
    index = msg.get('index')
    ifname = msg.get('ifname')
    forwarding = msg.get(('af_spec', 'af_inet', 'forwarding'))
    print(f'{index}: {ifname}: forwarding = {forwarding}')

ipr.close()
