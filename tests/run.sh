#!/bin/bash

cd "$( dirname "${BASH_SOURCE[0]}" )"
export PYTHONPATH="`pwd`:`pwd`/examples:`pwd`/examples/generic"
TOP=$(readlink -f $(pwd)/..)

#
# Load the configuration
#
. conf.sh

function deploy() {
    # Prepare test environment
    #
    # * make dist
    # * install packaged files into /tests
    # * copy examples into /tests
    # * run pep8 checks against /tests -- to cover test code also
    # * run nosetests
    #
    # It is important to test not in-place, but after `make dist`,
    # since in that case only those files will be tested, that are
    # included in the package.
    #
    cd $TOP
    [ -d ".git" ] && { # detect, if we run from git
        # ok, make tarball
        make dist >/dev/null
        mkdir "$TOP/tests/bin/"
        cp -a "$TOP/examples" "$TOP/tests/"
        cp -a "$TOP/cli/pyroute2-cli" "$TOP/tests/bin/"
        cp -a "$TOP/cli/ss2" "$TOP/tests/bin/"
        cd "$TOP/dist"
        tar xf *
        mv pyroute2*/pyroute2 "$TOP/tests/"
    } ||:  # or just give up and try to run as is
    cd "$TOP/tests/"
    $FLAKE8_PATH .
    ret=$?
    [ $ret -eq 0 ] && echo "flake8 ... ok"
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
    sysctl net.mpls.platform_labels=2048 2>/dev/null ||:
}


#
# Adjust paths
#
if which pyenv 2>&1 >/dev/null; then
    PYTHON_PATH=$(pyenv which $PYTHON)
    FLAKE8_PATH=$(pyenv which $FLAKE8)
    NOSE_PATH=$(pyenv which $NOSE)
else
    PYTHON_PATH=$(which $PYTHON)
    FLAKE8_PATH=$(which $FLAKE8)
    NOSE_PATH=$(which $NOSE)
fi

echo "8<------------------------------------------------"
echo "version: $VERSION"
echo "kernel: `uname -r`"
echo "python: $PYTHON_PATH [`$PYTHON_PATH --version 2>&1`]"
echo "flake8: $FLAKE8_PATH [`$FLAKE8_PATH --version 2>&1`]"
echo "nose: $NOSE_PATH [`$NOSE_PATH --version 2>&1`]"
echo "8<------------------------------------------------"


#
# Run tests
#
function get_module() {
    module=$1
    pattern=$2
    prefix="`echo $pattern | sed 's/:.*//'`"
    pattern="`echo $pattern | sed 's/[^:]\+://'`"
    [ "$prefix" = "$module" ] || exit 1
    echo $pattern
}

errors=0
avgtime=0
for i in `seq $LOOP`; do

    echo "[`date +%s`] iteration $i of $LOOP"

    deploy || {
        echo "flake 8 failed, sleeping for 30 seconds"
        sleep 30
        continue
    }

    for module in $MODULES; do
        [ -z "$MODULE" ] || {
            SUBMODULE="`get_module $module $MODULE`"
            RETVAL=$?
            [ $RETVAL -eq 0 ] || continue

        }
        tst1=`date +%s`
        uuid=`python -c "import uuid; print(str(uuid.uuid4()))"`
        echo "[$tst1][$uuid][$i/$LOOP]"
        if [ -z "$PDB" ]; then {
            $PYTHON $WLEVEL "$NOSE_PATH" -P -v \
                --with-coverage \
                --with-xunit \
                --cover-package=pyroute2 \
                $SKIP_TESTS \
                $COVERAGE $module/$SUBMODULE 2>&1 | tee tests.log
        } else {
            echo "tests log is not available with pdb" >tests.log
            $PYTHON $WLEVEL "$NOSE_PATH" -P -v $PDB \
                --with-coverage \
                --with-xunit \
                --cover-package=pyroute2 \
                $SKIP_TESTS \
                $COVERAGE $module/$SUBMODULE 2>&1
        } fi
        ret=${PIPESTATUS[0]}
        [ $ret -eq 0 ] || {
            errors=$(($errors + 1))
        }
        mv nosetests.xml xunit-$module.xmla
        tst2=`date +%s`
        [ $i -eq 1 ] && d=1 || d=2
        rtime=$(($tst2 - $tst1))
        avgtime=$((($avgtime + $rtime) / $d))
        echo "[$tst2][$uuid][$i/$LOOP] avgtime: $avgtime; iterations failed: $errors"
        [ -z "$REPORT" ] || {
            cat >tests.json << EOF
{"worker": "$WORKER",
 "run_id": "$uuid",
 "report": {"rtime": $rtime,
            "avgtime": $avgtime,
            "code": $ret,
            "run": $i,
            "total": $LOOP,
            "module": "$module/$SUBMODULE",
            "skip": "$SKIP_TESTS",
            "errors": $errors,
            "version": "$VERSION",
            "kernel": "`uname -r`",
            "python": "`$PYTHON_PATH --version 2>&1`"
            }
}
EOF
            curl -X POST \
                -d @tests.json \
                $REPORT
            echo " reports in the DB"
            curl -X PUT --data-binary @tests.log "$REPORT$WORKER/$uuid/" >/dev/null 2>&1
        }
    done
done
exit $errors
