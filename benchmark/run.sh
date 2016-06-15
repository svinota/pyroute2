#!/bin/bash

[ -z "$1" ] && {
    stop_label="0.3.6"
} || {
    stop_label=$1
}

function get_stop() {
    git log -1 $1 | awk '{print $2; exit}'
}

function mitata(){
    echo -n `git log | head -1 | awk '{print $2}' | head -c7`;
    sudo time -f ',%U,%S' python benchmark/ipdb.py 2>&1
}

stc=`get_stop $stop_label`
rm -f benchmark.log
export PYTHONPATH=`pwd`

while :; do {
    sudo make clean >/dev/null 2>&1
    mitata >>benchmark.log
    git checkout HEAD^
    [ "`git log | head -1 | awk '{print $2}'`" = "$stc" ] && break ||:
} done

git checkout master
