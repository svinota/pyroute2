#!/bin/bash

[ -z "$1" ] && {
    stop_label="0.4.0"
} || {
    stop_label=$1
}
modules="ipdb.py ipdb-route.py"

function get_stop() {
    git log -1 $1 | awk '{print $2; exit}'
}

function mitata(){
    echo `git log | head -1 | awk '{print $2}' | head -c7`
    for i in $modules; do {
        sudo time -f ',%U' python .benchmark/$i 2>&1
    } done
}

stc=`get_stop $stop_label`
mkdir .benchmark
for i in $modules; do {
    cp -f benchmark/$i .benchmark/
} done

rm -f benchmark.log
export PYTHONPATH="`pwd`"

while :; do {
    sudo make clean >/dev/null 2>&1
    mitata | sed -n 'H;$g;s/\n//gp' >>benchmark.log
    git checkout HEAD^
    [ "`git log | head -1 | awk '{print $2}'`" = "$stc" ] && break ||:
} done

sed -i -n 'G;h;$p' benchmark.log
rm -rf .benchmark

git checkout master
