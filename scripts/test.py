from iproute import IpRoute
ip = IpRoute()
print(ip.get_all_neighbors())
ip.stop()
