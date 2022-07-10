#!/usr/bin/env bash

#
# Utility to find Python
#

function list_pythons() {
    #
    # List all python binaries/shims/links in a directory $1
    #
    ls -1 $1/python* 2>/dev/null | grep -E 'python[0-9.]+$'
}

function check_valid_python() {
    #
    # Return "$VERSION $1" for $1 if it returns a valid version string
    # and has the required modules: ensurepip
    #
    # Note on versions: X.Y.Z... => XY, e.g.:
    #   3.6.10   -> 36
    #   3.10.1b1 -> 310
    #
    # This is required to sort versions correctly. The last version
    # byte is ignored.
    #
    for MODULE in ensurepip; do
        $1 -m $MODULE --version >/dev/null 2>&1 || return
    done
    VERSION=$( $1 -V 2>/dev/null |\
        grep -E '^Python [0-9a-z.]+$' |\
        sed 's/Python \([3-9]\.[0-9]\+\).*$/\1/;s/\.//' )
    if [ ! -z "$VERSION" ]; then
        echo $VERSION $1
    fi
}

function list_valid_pythons() {
    #
    # Filter only valid Pythons in a directory $1, ignoring pyenv shims
    # not pointing to an installed Python binary.
    #
    for PYTHON in $( list_pythons $1 ); do
        PYTHON=$( check_valid_python $PYTHON )
        if [ ! -z "$PYTHON" ]; then
            echo $PYTHON
        fi
    done
}

function iterate_path() {
    #
    # Iterate dirs in the $PATH variable, sorting Python versions
    # within each directory.
    #
    for DIR in $( echo $PATH | sed 's/:/ /g' ); do
        list_valid_pythons $DIR | sort -r -n
    done
}

#
# Take the first available Python with the highest version, respecting
# the $PATH variable.
#
# If operating in a venv, it will return the venv Python, despite the
# higher version may be available in the system directories.
#
iterate_path | head -1 | cut -d \  -f 2
