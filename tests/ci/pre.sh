#!/bin/bash

repo=`realpath $CIVM_WORKER_WORKDIR/../..`

pushd $CIVM_WORKER_MOUNT >/dev/null
    cd opt
    git clone $repo pyroute2 >/dev/null 2>&1
popd >/dev/null

[ -e $CIVM_WORKER_MOUNT/etc/rc.d ] && {
    cp $CIVM_WORKER_WORKDIR/rc.local $CIVM_WORKER_MOUNT/etc/rc.d/rc.local
} || {
    cp $CIVM_WORKER_WORKDIR/rc.local $CIVM_WORKER_MOUNT/etc/rc.local
}
