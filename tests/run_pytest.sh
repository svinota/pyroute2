#!/usr/bin/env bash

cd "$( dirname "${BASH_SOURCE[0]}" )"
TOP=$(readlink -f $(pwd)/..)

#
# Load the configuration
#
. conf.sh

#
# Choose the tests to run on this platform
#
case `uname -s` in
    OpenBSD)
        if [ -z "$PYTEST_PATH" ]; then
            export PYTEST_PATH=test_openbsd
        fi
        export MAKE=gmake
        ;;
    Linux)
        if [ -z "$PYTEST_PATH" ]; then
            export PYTEST_PATH=test_linux
        fi
        export MAKE=make
        ;;
esac

export PYTHONPATH="$WORKSPACE:$WORKSPACE/examples:$WORKSPACE/examples/generic"

# patch variables that differ between nosetests an pytest
[ -z "$PDB" ] || export PDB="--pdb"
[ -z "$COVERAGE" ] || export COVERAGE="--cov-report html --cov=pyroute2 --cov=pr2modules"


function setup_test() {
    ##
    # Prepare test environment
    #
    #
    # It is important to test not in-place, but after `make dist`,
    # since in that case only those files will be tested, that are
    # included in the package.
    #
    curl http://localhost:7623/v1/lock/ >/dev/null 2>&1 && \
    while [ -z "`curl -s -X POST --data test http://localhost:7623/v1/lock/ 2>/dev/null`" ]; do {
        sleep 1
    } done
    cd "$TOP"
    if [ "$1" = "test_minimal" ]; then {
        MAKE_TARGET="install-minimal"
    } else {
        MAKE_TARGET="install"
    } fi
    $MAKE $MAKE_TARGET python=$PYTHON make=$MAKE || return 1
    mkdir -p "$WORKSPACE"
    cp -a "$TOP/tests/"* "$WORKSPACE/"
    cp -a "$TOP/examples" "$WORKSPACE/"
    curl -X DELETE --data test http://localhost:7623/v1/lock/ >/dev/null 2>&1
    cd "$WORKSPACE"

    ##
    # Setup kernel parameters
    #
    [ "`uname -s`" = "Linux" -a "`id | sed 's/uid=[0-9]\+(\([A-Za-z]\+\)).*/\1/'`" = "root" ] && {
        echo "Running as root on Linux"
        ulimit -n 2048
        modprobe dummy 2>/dev/null ||:
        modprobe bonding 2>/dev/null ||:
        modprobe 8021q 2>/dev/null ||:
        modprobe mpls_router 2>/dev/null ||:
        modprobe mpls_iptunnel 2>/dev/null ||:
        modprobe l2tp_ip 2>/dev/null ||:
        modprobe l2tp_eth 2>/dev/null ||:
        modprobe l2tp_netlink 2>/dev/null ||:
        sysctl net.mpls.platform_labels=2048 >/dev/null 2>&1 ||:
    }
}


function cleanup_test() {
    cd "$TOP"
    $MAKE uninstall
}


function run_test() {
    errors=0
    avgtime=0
    for i in `seq $LOOP`; do

        echo "[`date +%s`] iteration $i of $LOOP"

        $PYTHON $WLEVEL \
            -m $PYTEST \
            --basetemp ./log \
            $PDB \
            $COVERAGE \
            --exitfirst \
            --verbose \
            --junitxml=junit.xml \
            $1
        ret=$?
        [ $ret -eq 0 ] || {
            errors=$(($errors + 1))
        }
        [ "$BREAK_ON_ERRORS" = "true" -a $errors -gt 0 ] && break ||:
    done
    return $errors
}


if [ -z "$VIRTUAL_ENV" -a -z "$PR2TEST_FORCE_RUN" ]; then {
    echo "Not in VirtualEnv and PR2TEST_FORCE_RUN is not set"
    exit 1
} fi

echo -n "Setup: $PYTEST_PATH ... "
setup_test $PYTEST_PATH || exit 1
echo "ok"
echo "Version: `cat $TOP/VERSION`"
echo "Kernel: `uname -r`"
run_test $PYTEST_PATH || exit 1
echo -n "Cleanup ... "
cleanup_test
echo "ok"
