'''
'''
from pyroute2.netlink.nfnetlink import nfgen_msg
from pyroute2.netlink.nfnetlink.nftsocket import (
    DATA_TYPE_ID_TO_NAME,
    DATA_TYPE_NAME_TO_INFO,
    NFT_MSG_DELCHAIN,
    NFT_MSG_DELRULE,
    NFT_MSG_DELSET,
    NFT_MSG_DELSETELEM,
    NFT_MSG_DELTABLE,
    NFT_MSG_GETCHAIN,
    NFT_MSG_GETRULE,
    NFT_MSG_GETSET,
    NFT_MSG_GETSETELEM,
    NFT_MSG_GETTABLE,
    NFT_MSG_NEWCHAIN,
    NFT_MSG_NEWRULE,
    NFT_MSG_NEWSET,
    NFT_MSG_NEWSETELEM,
    NFT_MSG_NEWTABLE,
    NFTSocket,
    nft_chain_msg,
    nft_rule_msg,
    nft_set_elem_list_msg,
    nft_set_msg,
    nft_table_msg,
)


class NFTables(NFTSocket):

    # TODO: documentation
    # TODO: tests
    # TODO: dump()/load() with support for json and xml

    def get_tables(self):
        return self.request_get(nfgen_msg(), NFT_MSG_GETTABLE)

    def get_chains(self):
        return self.request_get(nfgen_msg(), NFT_MSG_GETCHAIN)

    def get_rules(self):
        return self.request_get(nfgen_msg(), NFT_MSG_GETRULE)

    def get_sets(self):
        return self.request_get(nfgen_msg(), NFT_MSG_GETSET)

    #
    # The nft API is in the prototype stage and may be
    # changed until the release. The planned release for
    # the API is 0.5.2
    #

    def table(self, cmd, **kwarg):
        '''
        Example::

            nft.table('add', name='test0')
        '''
        commands = {
            'add': NFT_MSG_NEWTABLE,
            'create': NFT_MSG_NEWTABLE,
            'del': NFT_MSG_DELTABLE,
            'get': NFT_MSG_GETTABLE,
        }
        return self._command(nft_table_msg, commands, cmd, kwarg)

    def chain(self, cmd, **kwarg):
        '''
        Example::

            #
            # default policy 'drop' for input
            #
            nft.chain('add',
                      table='test0',
                      name='test_chain0',
                      hook='input',
                      type='filter',
                      policy=0)
        '''
        commands = {
            'add': NFT_MSG_NEWCHAIN,
            'create': NFT_MSG_NEWCHAIN,
            'del': NFT_MSG_DELCHAIN,
            'get': NFT_MSG_GETCHAIN,
        }
        # TODO: What about 'ingress' (netdev family)?
        hooks = {
            'prerouting': 0,
            'input': 1,
            'forward': 2,
            'output': 3,
            'postrouting': 4,
        }
        if 'hook' in kwarg:
            kwarg['hook'] = {
                'attrs': [
                    ['NFTA_HOOK_HOOKNUM', hooks[kwarg['hook']]],
                    ['NFTA_HOOK_PRIORITY', kwarg.pop('priority', 0)],
                ]
            }
        if 'type' not in kwarg:
            kwarg['type'] = 'filter'
        return self._command(nft_chain_msg, commands, cmd, kwarg)

    def rule(self, cmd, **kwarg):
        '''
        Example::

            from pyroute2.nftables.expressions import ipv4addr, verdict
            #
            # allow all traffic from 192.168.0.0/24
            #
            nft.rule('add',
                     table='test0',
                     chain='test_chain0',
                     expressions=(ipv4addr(src='192.168.0.0/24'),
                                  verdict(code=1)))
        '''
        commands = {
            'add': NFT_MSG_NEWRULE,
            'create': NFT_MSG_NEWRULE,
            'insert': NFT_MSG_NEWRULE,
            'replace': NFT_MSG_NEWRULE,
            'del': NFT_MSG_DELRULE,
            'get': NFT_MSG_GETRULE,
        }

        if 'expressions' in kwarg:
            expressions = []
            for exp in kwarg['expressions']:
                expressions.extend(exp)
            kwarg['expressions'] = expressions
        return self._command(nft_rule_msg, commands, cmd, kwarg)

    def sets(self, cmd, **kwarg):
        '''
        Example::
            nft.sets("add", table="filter", name="test0", key_type="ipv4_addr")
            nft.sets("get", table="filter", name="test0")
            nft.sets("del", table="filter", name="test0")
        '''
        commands = {
            'add': NFT_MSG_NEWSET,
            'get': NFT_MSG_GETSET,
            'del': NFT_MSG_DELSET,
        }

        if cmd in 'add':
            if 'key_len' not in kwarg:
                key_type, key_len, _ = DATA_TYPE_NAME_TO_INFO.get(
                    kwarg['key_type']
                )
                kwarg["key_type"] = key_type
                kwarg["key_len"] = key_len
            kwarg['id'] = 1

        return self._command(nft_set_msg, commands, cmd, kwarg)

    def set_elems(self, cmd, **kwarg):
        '''
        Example::
            nft.set_elems("add", table="filter", set="test0",
                          elements=["10.2.3.4", "10.4.3.2"])
            nft.set_elems("get", table="filter", set="test0")
            nft.set_elems("del", table="filter", set="test0",
                          elements=["10.2.3.4"])
        '''
        commands = {
            'add': NFT_MSG_NEWSETELEM,
            'get': NFT_MSG_GETSETELEM,
            'del': NFT_MSG_DELSETELEM,
        }
        set_info = self.sets("get", table=kwarg["table"], name=kwarg["set"])
        data_type_name = DATA_TYPE_ID_TO_NAME.get(
            set_info.get_attr("NFTA_SET_KEY_TYPE")
        )
        if data_type_name is not None:
            _, _, modifier = DATA_TYPE_NAME_TO_INFO[data_type_name]
            modifier = modifier()
            modifier.header = None
        else:
            modifier = None

        if cmd == "get":
            msg = nft_set_elem_list_msg()
            msg['attrs'] = [
                ["NFTA_SET_ELEM_LIST_TABLE", kwarg["table"]],
                ["NFTA_SET_ELEM_LIST_SET", kwarg["set"]],
            ]
            msg = self.request_get(msg, NFT_MSG_GETSETELEM)[0]
            elements = set()
            for elem in msg.get_attr('NFTA_SET_ELEM_LIST_ELEMENTS'):
                if modifier is not None:
                    # Need to find a better way
                    modifier.data = elem.get_attr(
                        'NFTA_SET_ELEM_KEY'
                    ).get_attr("NFTA_DATA_VALUE")
                    modifier.length = 4 + len(modifier.data)
                    modifier.decode()
                    elements.add(modifier.value)
            return elements

        data_type_name = DATA_TYPE_ID_TO_NAME.get(
            set_info.get_attr("NFTA_SET_KEY_TYPE")
        )
        if modifier is not None:
            elements = []
            for elem in kwarg.pop("elements"):
                modifier.value = elem
                modifier.encode()
                elements.append(modifier["value"])
        else:
            kwarg.pop("elements")

        kwarg["elements"] = [
            {
                'attrs': [
                    [
                        'NFTA_SET_ELEM_KEY',
                        {'attrs': [('NFTA_DATA_VALUE', elem)]},
                    ]
                ]
            }
            for elem in elements
        ]
        return self._command(nft_set_elem_list_msg, commands, cmd, kwarg)
