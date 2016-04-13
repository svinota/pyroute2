#!/bin/bash

mkdir -p $CIVM_WORKER_WORKDIR/results/$CIVM_WORKER_NAME
cp $CIVM_WORKER_MOUNT/opt/pyroute2/*log $CIVM_WORKER_WORKDIR/results/$CIVM_WORKER_NAME/
cp $CIVM_WORKER_MOUNT/opt/pyroute2/tests/*xml $CIVM_WORKER_WORKDIR/results/$CIVM_WORKER_NAME/
