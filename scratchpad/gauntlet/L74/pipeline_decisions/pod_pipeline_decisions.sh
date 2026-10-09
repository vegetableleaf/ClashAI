#!/bin/bash
# --pipeline-decisions SIM A/B on the RunPod pod (Linux, RoyaleSim). Pod-ready: every path / count is an env var with the layout of
# /workspace/POD_README.md as the default; nothing here touches the laptop, the live bot or any secret.
#
#   PHASE=pre    unit tests (fake-engine) + the REAL-engine smoke (the pending bodies / spell of extrapolate.pending_board can only be
#                exercised here: RoyaleSim is Linux-only). Fails fast; run it FIRST, it takes a few minutes.
#   PHASE=ab     the A/B: ARMS in parallel, each over census EVO + ladder LAD, paired by (census, tag).
#   PHASE=sum    pd_ab_summary.py (paired wins + the pro-pair profile + the acceptance bar).
#
# Pod defaults (POD_README.md, 2026-10-09): repo = the worktree /workspace/wt_pd of branch l74-pipeline-decisions (icebow/data and
# research/ext symlinked to /workspace/clashbot), venv /workspace/venv, results /workspace/results/pipeline, ROYALE_RUNTIME=20261006-linux.
# The WHOLE phase runs under `flock /workspace/cpu.lock` (shared pod: it queues behind the other jobs; <= 28 processes, TOTAL).
#   nohup bash scratchpad/gauntlet/L74/pipeline_decisions/pod_pipeline_decisions.sh > /workspace/results/pipeline/pre.out 2>&1 &     # PHASE=pre
#   PHASE=ab SEEDS=0:480 nohup bash .../pod_pipeline_decisions.sh > /workspace/results/pipeline/ab.out 2>&1 &
#   PHASE=sum bash .../pod_pipeline_decisions.sh
#
# Arms (decisions on 3 of the 4 are the deployed LIVE_OPTIONS bundle's; only --pipeline-* differs):
#   off  reference: the hard lock                                  (no flag)
#   pd0  --pipeline-decisions                                       the model's own gate, unchanged (replicates the failure mode if any)
#   pd1  --pipeline-decisions --pipeline-tau-delta 0.10             gate threshold +0.10 while a play is pending
#   pd2  --pipeline-decisions --pipeline-tau-delta 0.20
# Bar (pd_ab_summary.py): wins >= reference - 1.5 pp AND <=24-tick pairs per play <= 2x the pros' (0.058) AND elixir at play not lower
# by > 0.3 AND the Tornado share of second plays <= 2x the pros' (0.119). Earlier attempts (pipeline_plays v1/v2): OFF 628 vs 487 / 570 /
# 584 of 960 with 4.4x the pros' pairs and Tornado .50 vs .16 at second plays -- if pd0 shows that again, pd1/pd2 are the answer or the
# idea is closed; one change per experiment: the arms differ ONLY in the pipeline flags.
set -u
CB=${CB:-/workspace/wt_pd}; cd "$CB" || exit 2
PHASE=${PHASE:-pre}
# PD_NOLOCK=1 (lead decision 2026-10-09, `pre` only): run outside cpu.lock; the smoke then uses SMOKE_W (default 2) workers, one run at a
# time, plus the pytest process: at most 2 busy processes at any moment, nice 10.
if [ "$PHASE" != sum ] && [ -z "${PD_LOCKED:-}" ] && [ -z "${PD_NOLOCK:-}" ]; then        # one lock for the whole phase (arms run in parallel inside it)
  mkdir -p /workspace/results/pipeline
  echo "[$(date +%T)] waiting for /workspace/cpu.lock (PHASE=$PHASE)"
  exec flock /workspace/cpu.lock env PD_LOCKED=1 bash "$0" "$@"
fi
[ -n "${PD_NOLOCK:-}" ] && echo "[$(date +%T)] PD_NOLOCK: running outside cpu.lock, nice 10, <= 2 processes"
[ -n "${PD_LOCKED:-}" ] && echo "[$(date +%T)] got /workspace/cpu.lock (PHASE=$PHASE)"
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1       # POD_README.md: the runtime tag of the Linux build
PY=${PY:-/workspace/venv/bin/python}
HERE=scratchpad/gauntlet/L74/pipeline_decisions
OUT=${OUT:-/workspace/results/pipeline/pd_ab}; export OUT; mkdir -p "$OUT"; LOG=$OUT/run.log
TOTAL=${TOTAL:-28}                                   # <= 28 procs on the shared 32-vCPU pod (nproc shows the 255-core host)
SEEDS=${SEEDS:-0:480}
CK=${CK:-icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt}      # live checkpoint, sha 41b52a83
GEN1=${GEN1:-icebow/data/pipeline/gen_v1_s0/gen_s0.pt}
EVO=${EVO:-scratchpad/gauntlet/L70/pool_forms/loadable_decks.json}
LAD=${LAD:-scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json}
ARMS=${ARMS:-"off pd0 pd1 pd2"}
declare -A X=([off]="" [pd0]="--pipeline-decisions" [pd1]="--pipeline-decisions --pipeline-tau-delta 0.10" [pd2]="--pipeline-decisions --pipeline-tau-delta 0.20")
SIMFLAGS=$($PY $HERE/sim_flags.py scratchpad/gauntlet/L70/live/LIVE_OPTIONS)      # the deployed decision options, live-only switches removed

preflight() {
  for f in "$CK" "$GEN1" "$EVO" "$LAD"; do [ -e "$f" ] || { echo "MISSING $f"; exit 3; }; done
  echo "git $(git rev-parse HEAD 2>/dev/null) | ckpt sha256 $(sha256sum "$CK" | cut -c1-16) (live 41b52a83...) | flags: $SIMFLAGS"
  $PY -c "import pipeline.e1_eval as E, pipeline.search_s0 as S; print('imports ok', E.FOLLOW_MAX_OUT)" || exit 3
}

search() {   # search NAME CENSUS_FILE CENSUS_TAG WORKERS SEEDS [extra]
  local name=$1 d=$2 s=$3 w=$4 seeds=$5
  nice -n "${NICE:-10}" $PY -m pipeline.search_s0 --out "$OUT/${name}_$s" --seeds "$seeds" --opps gen --arms plain --gen "$CK" --opp-gen "$GEN1" \
    --forms-mode deck --device cpu --workers "$w" --tail-cap 7200 --tau-plain 0.35 --census "$d" --hero-abilities \
    --ability-policy v2 --opp-policy sample --opp-T 0.3 $SIMFLAGS --behaviour-telemetry --record-plays ${X[$name]} \
    > "$OUT/${name}_$s.log" 2>&1
  echo "$name $s seeds=$seeds rc=$? $(date +%T)" >> "$LOG"
}

case "$PHASE" in
pre)
  preflight
  # (1) fake-engine unit tests of the rules (laptop-identical) + the follow-up / default-parity ones they rest on
  nice -n "${NICE:-10}" $PY -m pytest -q -p no:cacheprovider pipeline/tests/test_e1_pipeline_decisions.py pipeline/tests/test_e1_follow_up.py \
      pipeline/tests/test_e1_action_delay.py pipeline/tests/test_league.py pipeline/tests/test_search_s0.py pipeline/tests/test_e1_follow_up_selfplay.py \
      --deselect pipeline/tests/test_e1_follow_up.py::TestLiveTwin || exit 4   # TestLiveTwin imports live_play -> cv2 (not on the pod)
  # (2) REAL-engine smoke: 4 seeds x {off, pd0} x {evo, lad}, 6 workers. Must run clean; then the checks below.
  for a in off pd0; do for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    search $a "$d" $s ${SMOKE_W:-2} 0:4; done; done
  $PY - <<'PYEOF' || exit 5
import json, glob, sys
bad = 0
for arm in ("off", "pd0"):
    for s in ("evo", "lad"):
        rows = [json.loads(l) for l in open(f"{__import__('os').environ.get('OUT', '/workspace/pd_ab')}/{arm}_{s}/matches.jsonl")]
        rows = [r for r in rows if r.get("arm") == "plain" and not r.get("skipped")]
        print(arm, s, "matches", len(rows))
        if not rows:
            bad += 1
            continue
        for r in rows:
            pd = r.get("pipeline_decisions")
            plays = r.get("own_plays") or []
            acc = sorted(q[1] for q in plays if q[3])
            if (arm == "pd0") != (pd is not None):
                print("  FLAG MISMATCH", r["tag"], pd); bad += 1
            if any(q[1] < q[0] for q in plays):
                print("  landing before decision", r["tag"]); bad += 1
            if pd is not None and pd.get("blocked_unaffordable", 0) + pd.get("blocked_slot_busy", 0) + pd.get("blocked_outstanding", 0) > 0:
                print("  VERDICT BLOCKED a model decision (the mask should make this unreachable):", r["tag"], pd); bad += 1
        if arm == "pd0":
            sec = sum((r["pipeline_decisions"] or {}).get("second_plays", 0) for r in rows)
            dec = sum((r["pipeline_decisions"] or {}).get("decisions_pending", 0) for r in rows)
            print("  pending decisions", dec, "second plays", sec, "(0 pending decisions = the mechanism never ran)")
            if dec == 0:
                bad += 1
sys.exit(1 if bad else 0)
PYEOF
  echo "SMOKE_PASS"
  ;;
ab)
  preflight
  n=$(echo $ARMS | wc -w); W=$(( TOTAL / (n * 2) )); [ $W -lt 1 ] && W=1       # arms x {evo, lad} all in parallel
  echo "arms: $ARMS | workers per run: $W | seeds $SEEDS" | tee -a "$LOG"
  for a in $ARMS; do search $a "$EVO" evo $W "$SEEDS" & search $a "$LAD" lad $W "$SEEDS" & done
  wait
  echo DONE >> "$LOG"
  ;;
sum)
  $PY $HERE/pd_ab_summary.py "$OUT" --ref off --arms "$(echo ${ARMS/off/} | xargs | tr ' ' ',')" --pros $HERE/pro_pairs24.json | tee "$OUT/summary.txt"
  ;;
*) echo "PHASE must be pre | ab | sum"; exit 2 ;;
esac
