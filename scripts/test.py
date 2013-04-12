from iproute import iproute
from pprint import pprint
from socket import AF_INET6

ip = iproute()


links = {}
for i in ip.get_all_links():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    del i['header']
    idx = i['index']
    links[idx] = i
    links[idx]['arp'] = []
    links[idx]['addr'] = []

for i in ip.get_all_neighbors():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    del i['header']
    links[i['ifindex']]['arp'].append(i)

for i in ip.get_all_neighbors(AF_INET6):
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    del i['header']
    links[i['ifindex']]['arp'].append(i)

for i in ip.get_all_addr():
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    del i['header']
    links[i['index']]['addr'].append(i)

for i in ip.get_all_addr(AF_INET6):
    for k in i['attributes']:
        i[k[0]] = k[1]
    del i['attributes']
    del i['header']
    links[i['index']]['addr'].append(i)

ip.stop()

pprint(links)
