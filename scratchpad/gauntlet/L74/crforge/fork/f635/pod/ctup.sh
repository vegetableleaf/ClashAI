#!/usr/bin/env bash
# usage: ctup.sh TAG -- F635c: core tests of the working tree on 16.635.3 then 16.402.22, no guard edit (the guard of the branch)
cd /workspace/f635 && ./ct.sh 16.635.3 /workspace/f635/ct_$1_635 > ct_$1.out 2>&1; ./ct.sh 16.402.22 /workspace/f635/ct_$1_402 >> ct_$1.out 2>&1; echo done >> ct_$1.out
