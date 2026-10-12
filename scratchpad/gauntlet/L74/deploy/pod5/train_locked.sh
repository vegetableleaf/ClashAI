#!/bin/bash
# pod 5: run pipeline.train_pending under /workspace/train.lock. Its ~13 GB dataset_cache_* dirs (the disk has ~7 GB free) are
# removed before and after, so only one cache exists at a time. cwd = /workspace/wt_tornado.  usage: train_locked.sh <train_pending args>
exec 9>/workspace/train.lock; flock 9
clean() { rm -rf /workspace/results/wk/*/icebow/dataset_cache_* /workspace/results/wk/ADAPTFIX/dataset_cache_*; }
clean
/workspace/venv/bin/python -m pipeline.train_pending "$@"; rc=$?
clean; exit $rc
