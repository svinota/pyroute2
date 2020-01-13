import socket
from pyroute2.ipset import IPSet, PortRange, PortEntry

ipset = IPSet()
ipset.create("foo", stype="hash:ip")
ipset.add("foo", "198.51.100.1", etype="ip")
ipset.add("foo", "198.51.100.2", etype="ip")
print(ipset.test("foo", "198.51.100.1"))   # True
print(ipset.test("foo", "198.51.100.10"))  # False
msg_list = ipset.list("foo")
for msg in msg_list:
    for attr_data in (msg
                      .get_attr('IPSET_ATTR_ADT')
                      .get_attrs('IPSET_ATTR_DATA')):
        for attr_ip_from in attr_data.get_attrs('IPSET_ATTR_IP_FROM'):
            for ipv4 in attr_ip_from.get_attrs('IPSET_ATTR_IPADDR_IPV4'):
                print("- " + ipv4)
ipset.destroy("foo")
ipset.close()


ipset = IPSet()
ipset.create("bar", stype="bitmap:port", bitmap_ports_range=(1000, 2000))
ipset.add("bar", 1001, etype="port")
ipset.add("bar", PortRange(1500, 2000), etype="port")
print(ipset.test("bar", 1600, etype="port"))  # True
print(ipset.test("bar", 2600, etype="port"))  # False
ipset.destroy("bar")
ipset.close()


ipset = IPSet()
protocol_tcp = socket.getprotobyname("tcp")
ipset.create("foobar", stype="hash:net,port")
port_entry_http = PortEntry(80, protocol=protocol_tcp)
ipset.add("foobar", ("198.51.100.0/24", port_entry_http), etype="net,port")
print(ipset.test("foobar",
                 ("198.51.100.1", port_entry_http), etype="ip,port"))   # True
port_entry_https = PortEntry(443, protocol=protocol_tcp)
print(ipset.test("foobar",
                 ("198.51.100.1", port_entry_https), etype="ip,port"))  # False
ipset.destroy("foobar")
ipset.close()
