#!/usr/bin/env bash
# usage: ctboth.sh TAG -- F635c: core tests on 16.402.22 then 16.635.3 (guard bypass for the run), results in ct_TAG_402/ ct_TAG_635/
cd /workspace/f635 && ./ct.sh 16.402.22 /workspace/f635/ct_$1_402 > ct_$1.out 2>&1; ./ct635.sh /workspace/f635/ct_$1_635 >> ct_$1.out 2>&1; echo done >> ct_$1.out
