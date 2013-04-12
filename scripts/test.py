from pyroute2.iproute import iproute
from pprint import pprint

ip = iproute()


links = {}
for i in ip.get_all_links():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    idx = i['index']
    links[idx] = i
    links[idx]['arp'] = []
    links[idx]['addr'] = []

for i in ip.get_all_neighbors():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    links[i['ifindex']]['arp'].append(i)

for i in ip.get_all_addr():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    links[i['index']]['addr'].append(i)

ip.stop()

pprint(links)
