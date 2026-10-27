#!/usr/bin/env bash
# usage: facade_test.sh TAG LIBDIR  -- F635b, pod 32657: compile the facade (CfCore.java) against one crforge lib and run
# pipeline/tests/test_crforge_core.py on it (HEAD pipeline in /workspace/f635b_facade/cb, RoyaleSim fin16-linux runtime,
# venvf16 for pytest)
F=/workspace/f635b_facade; B=$F/build_$1; rm -rf $B && mkdir -p $B
javac -d $B -cp "$2/*" $F/CfCore.java || exit 1
cd $F/cb && ROYALE_RUNTIME=fin16-linux PYTHONPATH=/workspace/cfspeed/pylib:$F/cb CRFORGE_LIB=$2 CRFORGE_FACADE_BUILD=$B \
  CRFORGE_TABLES=/workspace/cfspeed/crforge_cache/tables/16.402.22 timeout 1200 /workspace/venvf16/bin/python -m pytest -q pipeline/tests/test_crforge_core.py 2>&1 | tail -5
