from pyroute2 import IPRoute

with IPRoute() as ipr:
    for msg in ipr.get_links():
        print(msg)
