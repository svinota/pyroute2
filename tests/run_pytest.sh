#!/bin/bash

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
    DIST_NAME=pyroute2-$(git describe | sed 's/-[^-]*$//;s/-/.post/')
    echo -n "dist ... "
    make dist >/dev/null
    rm -rf "$WORKSPACE"
    mkdir -p "$WORKSPACE/bin"
    cp -a "$TOP/.flake8" "$WORKSPACE/"
    cp -a "$TOP/tests/"* "$WORKSPACE/"
    cp -a "$TOP/examples" "$WORKSPACE/"
    cp -a "$TOP/cli/pyroute2-cli" "$WORKSPACE/bin/"
    cp -a "$TOP/cli/ss2" "$WORKSPACE/bin/"
    cd "$TOP/dist"
    tar xf $DIST_NAME.tar.gz
    mv $DIST_NAME/pyroute2 "$WORKSPACE/"
    curl -X DELETE --data test http://localhost:7623/v1/lock/ >/dev/null 2>&1
    echo "ok"
    cd "$WORKSPACE/"
    echo -n "flake8 ... "
    $FLAKE8_PATH .
    ret=$?
    [ $ret -eq 0 ] && echo "ok"
    return $ret
}

#
# Install test requirements, if not installed.
#
function install_test_reqs() {
    which pip >/dev/null 2>&1 && pip install -q -r requirements.txt
}

if [ -z "$VIRTUAL_ENV" ]; then
    install_test_reqs
else
    # Install requirements only into manually-made virtualenvs.
    if [ -f "$VIRTUAL_ENV/bin/activate" ]; then
        source "$VIRTUAL_ENV/bin/activate"
        install_test_reqs
    fi
    echo "Running in VirtualEnv"
fi

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


#
# Adjust paths
#
if which pyenv 2>&1 >/dev/null; then
    PYTHON_PATH=$(pyenv which $PYTHON)
    FLAKE8_PATH=$(pyenv which $FLAKE8)
    PYTEST_PATH=$(pyenv which $PYTEST)
else
    PYTHON_PATH=$(which $PYTHON)
    FLAKE8_PATH=$(which $FLAKE8)
    PYTEST_PATH=$(which $PYTEST)
fi

echo "Version: $VERSION"
echo "Kernel: `uname -r`"


errors=0
avgtime=0
for i in `seq $LOOP`; do

    echo "[`date +%s`] iteration $i of $LOOP"

    deploy || {
        echo "flake 8 failed, sleeping for 30 seconds"
        sleep 30
        continue
    }

    $PYTHON $WLEVEL "$PYTEST_PATH" --basetemp ./log $PDB $COVERAGE
    ret=$?
    [ $ret -eq 0 ] || {
        errors=$(($errors + 1))
    }

done
exit $errors
