# -*- coding: utf-8 -*-
'''
Generic netlink
===============

Describe
'''
import errno
import logging
import os

from pyroute2.netlink import (
    CTRL_CMD_GETFAMILY,
    CTRL_CMD_GETPOLICY,
    GENL_ID_CTRL,
    NETLINK_ADD_MEMBERSHIP,
    NETLINK_DROP_MEMBERSHIP,
    NETLINK_GENERIC,
    NLM_F_ACK,
    NLM_F_DUMP,
    NLM_F_REQUEST,
    SOL_NETLINK,
    ctrlmsg,
)
from pyroute2.netlink.nlsocket import AsyncNetlinkSocket, SyncAPI


class AsyncGenericNetlinkSocket(AsyncNetlinkSocket):
    '''
    Low-level socket interface. Provides all the
    usual socket does, can be used in poll/select,
    doesn't create any implicit threads.
    '''

    mcast_groups = {}
    module_err_message = None
    module_err_level = 'error'
    _prid = None

    @property
    def prid(self):
        if self._prid is None:
            raise RuntimeError(
                'generic netlink protocol id is not obtained'
                ' yet, run bind() before placing any requests'
            )
        else:
            return self._prid

    async def bind(self, proto, msg_class, groups=0, pid=None, **kwarg):
        '''
        Bind the socket and performs generic netlink
        proto lookup. The `proto` parameter is a string,
        like "TASKSTATS", `msg_class` is a class to
        parse messages with.
        '''
        await super().bind(groups, pid, **kwarg)
        self.marshal.msg_map[GENL_ID_CTRL] = ctrlmsg
        msg = await self.discovery(proto)
        self._prid = msg.get_attr('CTRL_ATTR_FAMILY_ID')
        self.mcast_groups = dict(
            [
                (
                    x.get_attr('CTRL_ATTR_MCAST_GRP_NAME'),
                    x.get_attr('CTRL_ATTR_MCAST_GRP_ID'),
                )
                for x in msg.get_attr('CTRL_ATTR_MCAST_GROUPS', [])
            ]
        )
        self.marshal.msg_map[self.prid] = msg_class

    def add_membership(self, group):
        self.setsockopt(
            SOL_NETLINK, NETLINK_ADD_MEMBERSHIP, self.mcast_groups[group]
        )

    def drop_membership(self, group):
        self.setsockopt(
            SOL_NETLINK, NETLINK_DROP_MEMBERSHIP, self.mcast_groups[group]
        )

    async def discovery(self, proto):
        '''
        Resolve generic netlink protocol -- takes a string
        as the only parameter, return protocol description
        '''
        msg = ctrlmsg()
        msg['cmd'] = CTRL_CMD_GETFAMILY
        msg['version'] = 1
        msg['attrs'].append(['CTRL_ATTR_FAMILY_NAME', proto])
        msg['header']['type'] = GENL_ID_CTRL
        msg['header']['flags'] = NLM_F_REQUEST
        msg['header']['pid'] = self.pid
        msg.encode()
        self.sendto(msg.data, (0, 0))
        (msg,) = [x async for x in self.get()]
        err = msg['header'].get('error', None)
        if err is not None:
            if hasattr(err, 'code') and err.code == errno.ENOENT:
                err.extra_code = errno.ENOTSUP
                logger = getattr(logging, self.module_err_level)
                logger('Generic netlink protocol %s not found' % proto)
                logger('Please check if the protocol module is loaded')
                if self.module_err_message is not None:
                    logger(self.module_err_message)
            raise err
        return msg

    async def policy(self, proto):
        '''
        Extract policy information for a generic netlink protocol -- takes
        a string as the only parameter, return protocol policy
        '''
        self.marshal.msg_map[GENL_ID_CTRL] = ctrlmsg
        msg = ctrlmsg()
        msg['cmd'] = CTRL_CMD_GETPOLICY
        msg['attrs'].append(['CTRL_ATTR_FAMILY_NAME', proto])
        return tuple(
            [
                x
                async for x in await self.nlm_request(
                    msg,
                    msg_type=GENL_ID_CTRL,
                    msg_flags=NLM_F_REQUEST | NLM_F_DUMP | NLM_F_ACK,
                )
            ]
        )


class GenericNetlinkSocket(SyncAPI):
    def __init__(
        self,
        family=NETLINK_GENERIC,
        port=None,
        pid=None,
        fileno=None,
        sndbuf=1048576,
        rcvbuf=1048576,
        rcvsize=16384,
        all_ns=False,
        async_qsize=None,
        nlm_generator=True,
        target='localhost',
        ext_ack=False,
        strict_check=False,
        groups=0,
        nlm_echo=False,
        netns=None,
        flags=os.O_CREAT,
        libc=None,
        use_socket=None,
        use_event_loop=None,
        telemetry=None,
    ):
        self.asyncore = AsyncGenericNetlinkSocket(
            family=family,
            port=port,
            pid=pid,
            fileno=fileno,
            sndbuf=sndbuf,
            rcvbuf=rcvbuf,
            rcvsize=rcvsize,
            all_ns=all_ns,
            target=target,
            ext_ack=ext_ack,
            strict_check=strict_check,
            groups=groups,
            nlm_echo=nlm_echo,
            netns=netns,
            flags=flags,
            libc=libc,
            use_socket=use_socket,
            use_event_loop=use_event_loop,
            telemetry=telemetry,
        )
        self.status['nlm_generator'] = False
        self.asyncore.status['event_loop'] = 'new'
        self.asyncore.local.keep_event_loop = True
        self.asyncore.event_loop.run_until_complete(
            self.asyncore.setup_endpoint()
        )

    @property
    def prid(self):
        return self.asyncore.prid

    @property
    def mcast_groups(self):
        return self.asyncore.mcast_groups

    def bind(self, proto, msg_class, groups=0, pid=None, **kwarg):
        return self._run_with_cleanup(
            self.asyncore.bind, 'bind', proto, msg_class, groups, pid, **kwarg
        )

    def add_membership(self, group):
        return self.asyncore.add_membership(group)

    def drop_membership(self, group):
        return self.asyncore.drop_membership(group)

    def discovery(self, proto):
        return self._run_with_cleanup(
            self.asyncore.discovery, 'discovery', proto
        )

    def policy(self, proto):
        return self._run_with_cleanup(self.asyncore.policy, 'policy', proto)

    def nlm_request(
        self,
        msg,
        msg_type,
        msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
        terminate=None,
        callback=None,
        parser=None,
    ):
        ret = self._generate_with_cleanup(
            self.asyncore.nlm_request,
            'nl-req',
            msg,
            msg_type,
            msg_flags,
            terminate,
            callback,
            parser,
        )
        if self.status['nlm_generator']:
            return ret
        return tuple(ret)

    def get(self, msg_seq=0, terminate=None, callback=None, noraise=False):

        async def collect_data():
            return [
                i
                async for i in self.asyncore.get(
                    msg_seq, terminate, callback, noraise
                )
            ]

        return self._run_with_cleanup(collect_data, 'nl-get')
