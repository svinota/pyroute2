#!/bin/bash

export PYTHONPATH="`pwd`:`pwd`/examples"
echo $PYTHONPATH

# Prepare test environment
#
# * make dist
# * install packaged files into /tests
# * copy examples into /tests
# * run pep8 checks against /tests -- to cover test code also
# * run nosetests
#
# It is important to test not in-place, but after `make dist`,
# since in that case only those files will be tests, that
# are included in the package.
#
cd ../dist
    tar xf *
    mv pyroute2*/pyroute2 ../tests/
cd ../
    cp -a examples ./tests/
cd ./tests/

# Install test requirements, if not installed. If the user
# is not root and all requirements are met, this step will
# be safely skipped.
#
pip install -q -r requirements.txt


[ -z "$1" ] && {
    echo "Test module isn't specified"
    exit 1
}

[ -z "$VIRTUAL_ENV" ] || {
    . $$VIRTUAL_ENV/bin/activate ;
    echo "Running in VirtualEnv"
}

[ "`id | sed 's/uid=[0-9]\+(\([A-Za-z]\+\)).*/\1/'`" = "root" ] && {
    echo "Running as root"
    ulimit -n 2048
    modprobe dummy 2>/dev/null ||:
    modprobe bonding 2>/dev/null ||:
    modprobe 8021q 2>/dev/null ||:
}

[ -z "$PYTHON" ] && export PYTHON=python
[ -z "$NOSE" ] && export NOSE=nosetests
[ -z "$FLAKE8" ] && export FLAKE8=flake8
[ -z "$WLEVEL" ] || export WLEVEL="-W $WLEVEL"
[ -z "$PDB" ] || export PDB="--pdb --pdb-failures"
[ -z "$COVERAGE" ] || export COVERAGE="--cover-html"
[ -z "$SKIP_TESTS" ] || export SKIP_TESTS="--exclude $SKIP_TESTS"
[ -z "$MODULE" ] || export MODULE=`echo $MODULE | sed -n '/:/{p;q};s/$/:/p'`

export PVERSION=`$PYTHON -c 'import sys; print(sys.version_info[0])'`
[ $PVERSION -eq 2 ] && {
    export PEP8EXC="--exclude=pyroute2/netns/process/base_p3.py"
} || {
    export PEP8EXC="--exclude=pyroute2/netns/process/base_p2.py"
}

echo "python: `which $PYTHON` [`$PYTHON --version 2>&1`]"
echo "flake8: `which $FLAKE8` [`$FLAKE8 --version 2>&1`]"
echo "nose: `which $NOSE` [`$NOSE --version 2>&1`]"
echo "pversion: $PVERSION"
echo "pep8 exclude list: $PEP8EXC"

$PYTHON `which $FLAKE8` $PEP8EXC . && echo "flake8 ... ok" || exit 254
[ -z "$TRAVIS" ] || exit 0

function get_module() {
    module=$1
    pattern=$2
    prefix="`echo $pattern | sed 's/:.*//'`"
    pattern="`echo $pattern | sed 's/[^:]\+://'`"
    [ "$prefix" = "$module" ] || exit 1
    echo $pattern
}
for module in $@; do
    [ -z "$MODULE" ] || {
        SUBMODULE="`get_module $module $MODULE`"
        RETVAL=$?
        [ $RETVAL -eq 0 ] || continue

    }
    $PYTHON $WLEVEL `which $NOSE` -P -v $PDB \
        --with-coverage \
        --cover-package=pyroute2 \
        $SKIP_TESTS \
        $COVERAGE $module/$SUBMODULE || exit 252
done
