#!/usr/bin/env bash
# Weekly crforge upstream sync with a three-part gate (owner request 2026-10-27). Run on pod 33920:
#   bash upstream_sync.sh [DATE]          (DATE default: today, UTC, YYYYMMDD)
# 1. fetch upstream into /workspace/crforge_fork, list the commits past the pin and the paths they touch;
# 2. branch clashbot-upstream-DATE from clashbot-fix (our patches) and merge upstream/main (conflicts stop the run);
# 3. gate: (a) crforge core tests, 0 failures; (b) SME live pilot on the 109 unflagged matches (current extract,
#    /workspace/pilot/inputs_v2) vs the pin's latest run: no exact match lost; (c) J7 crown sequence, crforge_force arm,
#    deck8 subset (401), not worse than the pin's (0.808 on 2026-10-27; CI overlap is fine).
# The pin (/workspace/crforge) is never modified. Promotion to a new pin is a manual step after a PASS (CRFORGE_S0.md).
set -euo pipefail
DATE=${1:-$(date -u +%Y%m%d)}
F=/workspace/crforge_fork; OUT=/workspace/upstream_sync/$DATE; mkdir -p $OUT
PIN=ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0
SME=/workspace/pilot/sme; LIVE=/workspace/pilot/sme_live; J7=/workspace/pilot/j7
BASE_SME=${BASE_SME:-$LIVE/run12}          # the pin's latest SME run with the same inputs and comparator
T=/workspace/crforge_cache/tables/16.402.22
GRADLE="./gradlew --no-daemon --max-workers=8 -Pcrforge.cache=/workspace/crforge_cache -Pcrforge.assetSource=file:///workspace/crforge_cache/none"

cd $F
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream https://github.com/voonhous/crforge.git
git fetch -q upstream
echo "commits past the pin: $(git rev-list --count $PIN..upstream/main)" | tee $OUT/commits.txt
git log --reverse --stat --format='== %h %s' $PIN..upstream/main >> $OUT/commits.txt
echo "paths outside docs/README:" | tee -a $OUT/commits.txt
git diff --stat $PIN upstream/main -- . ':(exclude)docs' ':(exclude)README.md' | tail -20 | tee -a $OUT/commits.txt

B=clashbot-upstream-$DATE
git checkout -q clashbot-fix
git branch -D $B >/dev/null 2>&1 || true
git checkout -q -b $B
if ! git merge --no-edit -q upstream/main; then
  git diff --name-only --diff-filter=U | tee $OUT/conflicts.txt; echo "CONFLICTS: stop"; exit 2
fi
git log -1 --format='merged %H' | tee $OUT/merged.txt

# (a) build + core tests
$GRADLE :env:installDist > $OUT/build.log 2>&1
$GRADLE :core:test > $OUT/coretest.log 2>&1 || true
python3 -c "
import glob, xml.etree.ElementTree as ET
t=f=e=s=0
for p in glob.glob('core/build/test-results/test/*.xml'):
    r=ET.parse(p).getroot(); t+=int(r.get('tests')); f+=int(r.get('failures')); e+=int(r.get('errors')); s+=int(r.get('skipped'))
print('core tests', t, 'failures', f, 'errors', e, 'skipped', s)" | tee $OUT/coretest.txt
L=$F/env/build/install/env/lib

# determinism hash of the fork build (Probe from /workspace/seeds, compiled against it)
mkdir -p $OUT/probe && javac -d $OUT/probe -cp "$L/*" /workspace/seeds/Probe.java
java -cp "$L/*:$OUT/probe" Probe $T determinism > $OUT/det.txt 2>&1 || true

# (b) SME live pilot
mkdir -p $OUT/smebuild && javac -d $OUT/smebuild -cp "$L/*" $SME/SmeRun.java
( cd $SME && SME_LIB=$L SME_BUILD=$OUT/smebuild SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=$SME/repr_v1.json SME_THREADS=4 \
    python3 sme_live.py all --workers 12 --inputs /workspace/pilot/inputs_v2/inputs_rngfree.jsonl --frames $LIVE/frames2 \
    --out $OUT/sme > $OUT/sme.log 2>&1 )
( cd $SME && python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE_SME $OUT/sme ) | tee $OUT/sme_cmp.txt

# (c) J7 crown sequence, crforge_force lo/hi on plans_x, scored with the pin's other arms for the paired lines
mkdir -p $OUT/j7build $OUT/j7runs && javac -d $OUT/j7build -cp "$L/*" $J7/src/J7Run.java
: > $OUT/j7jobs.txt
for t in lo hi; do mkdir -p $OUT/j7runs/crforge_force_$t
  for p in $(cat $J7/plans_x/index.txt); do echo "$J7/plans_x/$p.json force $t $OUT/j7runs/crforge_force_$t/$p.json" >> $OUT/j7jobs.txt; done
done
( cd $J7 && java -Xmx8g -cp "$L/*:$OUT/j7build" org.crforge.core.battle.match.J7Run $T $OUT/j7jobs.txt 12 ) > $OUT/j7run.log 2>&1
for a in fin15_force_lo fin15_force_hi; do ln -sfn $J7/runs_x/$a $OUT/j7runs/$a; done
# j7.py from the repo copy in cb/ (the top-level copy resolves its repo root from its own path and fails)
( cd $J7 && PYTHONPATH=$J7/cb python3 cb/scratchpad/gauntlet/L74/crforge/pilot/j7/j7.py score --truth truth_j7x.jsonl \
    --runs $OUT/j7runs --inputs inputs_j7x.jsonl --out $OUT/j7score ) > $OUT/j7score.log 2>&1
grep -A3 'subset deck8' $OUT/j7score/SCORE.md | grep -m1 '^| crforge_force' | tee $OUT/j7_line.txt
for t in lo hi; do   # byte-identity of the crforge arm against the pin's runs (identical = no behaviour change)
  echo "$t pin $(cat $J7/runs_x/crforge_force_$t/*.json | sha256sum | cut -c1-16) new $(cat $OUT/j7runs/crforge_force_$t/*.json | sha256sum | cut -c1-16)"
done | tee $OUT/j7_identity.txt
echo "done: $OUT"
