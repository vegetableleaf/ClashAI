#!/usr/bin/env bash
# Weekly crforge upstream sync (owner request 2026-10-27). Since CF-MAIN (2026-10-28) it merges upstream onto clashbot-main,
# the one tested branch (fork/MAIN.md); before that it merged onto clashbot-fix on pod 33920 (see git history).
# Run on pod 30408 (the fork that holds clashbot-main), with fork/main/pod/*.sh + CloneProbe.java, sweep_sum.py, grades_cmp.py
# in /workspace/cfmain:
#   bash upstream_sync.sh [DATE]          (DATE default: today, UTC, YYYYMMDD)
# 1. fetch upstream into /workspace/f635/crforge_fork, list the upstream commits past clashbot-main and the paths they touch;
# 2. new worktree /workspace/upstream_sync/DATE/crforge_fork on branch clashbot-upstream-DATE from clashbot-main, merge
#    upstream/main (conflicts stop the run); no other worktree or branch is touched;
# 3. gates on this pod: WT=<that worktree> gates30408.sh sync_DATE (core tests on 16.402.22 and 16.635.3, 0 failures; libs
#    plain + TickProbe into /workspace/crforge_main/SHA8/; determinism hashes; HF 20k fault
#    sample, no more faults than clashbot-main's, per replay vs FBASE = clashbot-main's f20k run, see MAIN.md).
# 4. then, by hand (libs reach other pods through the laptop: fork/main/ship_main.sh SHA8):
#    SME on pod 32657: sme_gate.sh sync_DATE /workspace/crforge_main/SHA8/tickprobe/lib (dev 109/109, 0 regressions, vs
#    clashbot-main's SME runs: set the base runs in sme_gate.sh); J7 crown sequence on pod 33920 as part (c) of this
#    script's 10-27 version (crforge_force arm, deck8 subset, not worse than the pin's 0.808).
# Promotion after every gate passes (manual): git -C /workspace/f635/crforge_fork branch -f clashbot-main
# clashbot-upstream-DATE, ship_main.sh, then MAIN.md and CRFORGE_S0.md.
set -euo pipefail
DATE=${1:-$(date -u +%Y%m%d)}
F=/workspace/f635/crforge_fork; OUT=/workspace/upstream_sync/$DATE; WT=$OUT/crforge_fork; mkdir -p $OUT
cd $F
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream https://github.com/voonhous/crforge.git
git fetch -q upstream
N=$(git rev-list --count clashbot-main..upstream/main)
echo "upstream commits past clashbot-main: $N (merge base $(git merge-base clashbot-main upstream/main))" | tee $OUT/commits.txt
git log --reverse --stat --format='== %h %s' clashbot-main..upstream/main >> $OUT/commits.txt
echo "paths outside docs/README:" | tee -a $OUT/commits.txt
git diff --stat clashbot-main...upstream/main -- . ':(exclude)docs' ':(exclude)README.md' | tail -20 | tee -a $OUT/commits.txt
[ "$N" = 0 ] && { echo "nothing to merge"; exit 0; }

B=clashbot-upstream-$DATE
git worktree remove --force $WT 2>/dev/null || true
git branch -D $B >/dev/null 2>&1 || true
git worktree add -q -b $B $WT clashbot-main
cd $WT
if ! git -c user.name=vegetableleaf -c user.email=vegetableleaf@users.noreply.github.com merge --no-edit -q upstream/main; then
  git diff --name-only --diff-filter=U | tee $OUT/conflicts.txt; echo "CONFLICTS: stop"; exit 2
fi
git log -1 --format='merged %H' | tee $OUT/merged.txt

WT=$WT FBASE=${FBASE:-/workspace/d1c/f20k_cfclone2} bash /workspace/cfmain/gates30408.sh sync_$DATE
G=/workspace/cfmain/g_sync_$DATE
cat $G/ct.txt $G/det.txt $G/faults_vs_base.txt | tee $OUT/gates.txt
grep -m1 '"faults"' $G/faults_summary.json | tee -a $OUT/gates.txt
echo "next: ship_main.sh SHA8 (laptop); clone_sweep.sh on 33920 (cp_clone_refusals.txt empty); sme_gate.sh on 32657" | tee -a $OUT/gates.txt
echo "done: $OUT (then SME on 32657 and J7 on 33920, see the header)"
