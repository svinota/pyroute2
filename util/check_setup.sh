#!/usr/bin/env bash

if [ -z "$1" ]; then {
    PYTHON=`which python 2>/dev/null`
    PYTHON2=`which python2 2>/dev/null`
    PYTHON3=`which python3 2>/dev/null`
} else {
    PYTHON=$1
} fi

get_version() {
    $1 -m $2 --version | sed 's/^[[:alpha:][:space:]]\+//;s/ .*//;q'
}

##
# check python versions
#
if [ -z "$PYTHON" ]; then {
    # no "just python", look for python3
    PYTHON=$PYTHON3
} fi

if [ -z "$PYTHON" ]; then {
    # no python3, use python2
    PYTHON=$PYTHON2
    if [ -n "$PYTHON2" ]; then {
        echo "Python 3 is not available, using Python 2" 1>&2
        echo -e "!\n! NB: pyroute2 is not supported with Python < 3.6, use at your own risk\n!" 1>&2
    } fi
} fi

if [ -z "$PYTHON" ]; then {
    echo "Python not available, exiting" 1>&2
    exit 1
} fi

##
# check virtualenv
#
if [ -z "$VIRTUAL_ENV" ]; then {
    echo "Not in VirtualEnv, some targets will not work" 1>&2
    HAS_VENV="false"
} else {
    HAS_VENV="true"
} fi

##
# check required modules
#
PIP_VERSION=`get_version $PYTHON pip`
TWINE_VERSION=`get_version $PYTHON twine`

if [ -z "$PIP_VERSION" ]; then {
    echo "pip not found, make sure pip is installed" 1>&2
    HAS_PIP="false"
} else {
    HAS_PIP="true"
} fi

if [ -z "$TWINE_VERSION" ]; then {
    echo "twine not found, packaging will not work" 1>&2
    HAS_TWINE="false"
} else {
    HAS_TWINE="true"
} fi

cat <<EOF | tee Makefile.in
python ?= $PYTHON
has_pip ?= $HAS_PIP
has_twine ?= $HAS_TWINE
has_venv ?= $HAS_VENV
EOF
