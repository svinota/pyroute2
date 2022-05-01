#!/bin/bash -x

cd "$( dirname "${BASH_SOURCE[0]}" )"
TOP=$(readlink -f $(pwd)/..)

#
# Load the configuration
#
. conf.sh

export PYTHONPATH="$WORKSPACE:$WORKSPACE/examples:$WORKSPACE/examples/generic"

# patch variables that differ between nosetests an pytest
[ -z "$PDB" ] || export PDB="--pdb"
[ -z "$COVERAGE" ] || export COVERAGE="--cov-report html --cov=pyroute2"

function deploy() {
    # Prepare test environment
    #
    # * make dist
    # * install packaged files into $WORKSPACE
    # * copy examples into $WORKSPACE
    # * run pep8 checks against $WORKSPACE -- to cover test code also
    # * run tests
    #
    # It is important to test not in-place, but after `make dist`,
    # since in that case only those files will be tested, that are
    # included in the package.
    #
    curl http://localhost:7623/v1/lock/ >/dev/null 2>&1 && \
    while [ -z "`curl -s -X POST --data test http://localhost:7623/v1/lock/ 2>/dev/null`" ]; do {
        sleep 1
    } done
    cd $TOP
    DIST_VERSION=$(git describe | sed 's/-[^-]*$//;s/-/.post/')
    echo -n "dist ... "
    make dist python=$PYTHON
    rm -rf "$WORKSPACE"
    mkdir -p "$WORKSPACE/bin"
    cp -a "$TOP/tests/"* "$WORKSPACE/"
    cp -a "$TOP/examples" "$WORKSPACE/"
    cp -a "$TOP/cli/pyroute2-cli" "$WORKSPACE/bin/"
    cp -a "$TOP/cli/ss2" "$WORKSPACE/bin/"
    cd "$TOP/dist"
    rm -f pyroute2.minimal*$DIST_VERSION*
    $PYTHON -m pip install pyroute2*$DIST_VERSION*
    curl -X DELETE --data test http://localhost:7623/v1/lock/ >/dev/null 2>&1
    echo "ok"
    cd "$WORKSPACE/"
}

if [ -z "$VIRTUAL_ENV" -a -z "$PR2TEST_FORCE_RUN" ]; then {
    echo "Not in VirtualEnv and PR2TEST_FORCE_RUN is not set"
    exit 1
} fi

echo "Version: `cat $TOP/VERSION`"
echo "Kernel: `uname -r`"

deploy || exit 1

#
# Setup kernel parameters
#
[ "`id | sed 's/uid=[0-9]\+(\([A-Za-z]\+\)).*/\1/'`" = "root" ] && {
    echo "Running as root"
    ulimit -n 2048
    modprobe dummy 2>/dev/null ||:
    modprobe bonding 2>/dev/null ||:
    modprobe 8021q 2>/dev/null ||:
    modprobe mpls_router 2>/dev/null ||:
    modprobe mpls_iptunnel 2>/dev/null ||:
    sysctl net.mpls.platform_labels=2048 >/dev/null 2>&1 ||:
}


errors=0
avgtime=0
for i in `seq $LOOP`; do

    echo "[`date +%s`] iteration $i of $LOOP"

    $PYTHON $WLEVEL -m $PYTEST --basetemp ./log $PDB $COVERAGE
    ret=$?
    [ $ret -eq 0 ] || {
        errors=$(($errors + 1))
    }

done
for i in `$PYTHON -m pip list | awk '/pyroute2/ {print $1}'`; do {
    $PYTHON -m pip uninstall -y $i
} done
exit $errors
