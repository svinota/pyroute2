import uuid

import pytest
from pr2test.context_manager import make_test_matrix
from pr2test.marks import require_root
from pr2test.tools import address_exists, interface_exists

from pyroute2.ndb.transaction import (
    CheckProcess,
    CheckProcessException,
    Not,
    PingAddress,
)

pytestmark = [require_root()]


def test_check_process_basic():
    test = CheckProcess('true')
    assert test.return_code is None
    test.commit()
    test.rollback()
    assert test.return_code == 0


def test_check_process_fail():
    test = CheckProcess('false')
    assert test.return_code is None
    with pytest.raises(CheckProcessException):
        test.commit()
    assert test.return_code == 1


def test_check_process_file_not_found():
    test = CheckProcess(str(uuid.uuid4()))
    assert test.return_code is None
    with pytest.raises(FileNotFoundError):
        test.commit()
    assert test.return_code is None


def test_check_process_timeout():
    test = CheckProcess('sleep 10', timeout=1)
    with pytest.raises(CheckProcessException):
        test.commit()


@pytest.mark.parametrize('command', (None, '', -1, ['s1', 's2'], True))
def test_check_process_wrong_command(command):
    with pytest.raises(TypeError):
        CheckProcess(command)


def test_negation():
    test = CheckProcess('false')
    with pytest.raises(CheckProcessException):
        test.commit()
    Not(test).commit()


def test_ping_ok():
    test = PingAddress('127.0.0.1')
    test.commit()


def test_ping_unreachable():
    test = PingAddress('128.0.0.1')
    with pytest.raises(CheckProcessException):
        test.commit()


def test_ping_unknown():
    test = PingAddress(str(uuid.uuid4()))
    with pytest.raises(CheckProcessException):
        test.commit()


test_matrix = make_test_matrix(
    targets=['local', 'netns'], dbs=['sqlite3/:memory:', 'postgres/pr2test']
)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_multiple_interfaces(context):

    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    (
        context.ndb.begin()
        .push(
            context.ndb.interfaces.create(ifname=ifname1, kind='dummy')
            .set(state='up')
            .set(address='00:11:22:aa:aa:aa')
            .add_ip(address=ipaddr1, prefixlen=24),
            context.ndb.interfaces.create(ifname=ifname2, kind='dummy')
            .set(state='up')
            .set(address='00:11:22:bb:bb:bb')
            .add_ip(address=ipaddr2, prefixlen=24),
        )
        .commit()
    )

    assert interface_exists(
        context.netns, ifname=ifname1, address='00:11:22:aa:aa:aa'
    )
    assert interface_exists(
        context.netns, ifname=ifname2, address='00:11:22:bb:bb:bb'
    )
    assert address_exists(context.netns, ifname=ifname1, address=ipaddr1)
    assert address_exists(context.netns, ifname=ifname2, address=ipaddr2)


@pytest.mark.parametrize('context', test_matrix, indirect=True)
def test_check_context_manager(context):
    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    with context.ndb.begin() as ctx:
        ctx.push(context.ndb.interfaces.create(ifname=ifname1, kind='dummy'))
        ctx.push(context.ndb.interfaces.create(ifname=ifname2, kind='dummy'))
    assert interface_exists(context.netns, ifname=ifname1)
    assert interface_exists(context.netns, ifname=ifname2)


def test_intrefaces_ping(context):

    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    with pytest.raises(CheckProcessException):
        PingAddress(ipaddr1).commit()

    with pytest.raises(CheckProcessException):
        PingAddress(ipaddr2).commit()

    (
        context.ndb.begin()
        .push(
            context.ndb.interfaces.create(ifname=ifname1, kind='dummy')
            .set(state='up')
            .add_ip(address=ipaddr1, prefixlen=24),
            context.ndb.interfaces.create(ifname=ifname2, kind='dummy')
            .set(state='up')
            .add_ip(address=ipaddr2, prefixlen=24),
            PingAddress(ipaddr1, log=context.ndb.log.channel('util')),
            PingAddress(ipaddr2, log=context.ndb.log.channel('util')),
        )
        .commit()
    )

    assert interface_exists(ifname=ifname1)
    assert interface_exists(ifname=ifname2)
    assert address_exists(ifname=ifname1, address=ipaddr1)
    assert address_exists(ifname=ifname2, address=ipaddr2)


def test_intrefaces_ping_fail(context):

    ifname1 = context.new_ifname
    ifname2 = context.new_ifname
    ipaddr1 = context.new_ipaddr
    ipaddr2 = context.new_ipaddr

    with pytest.raises(CheckProcessException):
        PingAddress(ipaddr1).commit()

    with pytest.raises(CheckProcessException):
        PingAddress(ipaddr2).commit()

    (
        context.ndb.begin()
        .push(
            context.ndb.interfaces.create(
                ifname=ifname1, kind='dummy', state='up'
            ),
            context.ndb.interfaces.create(
                ifname=ifname2, kind='dummy', state='up'
            ),
        )
        .commit()
    )

    assert interface_exists(ifname=ifname1)
    assert interface_exists(ifname=ifname2)
    assert not address_exists(address=ipaddr1)
    assert not address_exists(address=ipaddr2)

    with pytest.raises(CheckProcessException):
        (
            context.ndb.begin()
            .push(
                context.ndb.interfaces[ifname1].add_ip(
                    address=ipaddr1, prefixlen=24
                ),
                PingAddress(ipaddr2, log=context.ndb.log.channel('util')),
            )
            .commit()
        )

    assert not address_exists(address=ipaddr1)
    assert not address_exists(address=ipaddr2)
