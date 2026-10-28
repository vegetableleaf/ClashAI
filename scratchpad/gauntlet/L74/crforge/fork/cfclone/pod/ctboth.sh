#!/usr/bin/env bash
# CF-CLONE: full core tests of the cfclone worktree on 16.402.22 then 16.635.3
cd /workspace/cfclone && bash tt.sh 16.402.22 /workspace/cfclone/ct_402.log > ct_both.out 2>&1; bash tt.sh 16.635.3 /workspace/cfclone/ct_635.log >> ct_both.out 2>&1; echo done >> ct_both.out
