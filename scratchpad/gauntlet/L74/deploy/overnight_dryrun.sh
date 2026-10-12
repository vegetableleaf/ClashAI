#!/bin/bash
# Offline test of overnight_orchestrator.sh (DRY=1: no pod, no live, no Discord; fake SUMMARY files + fake live logs). Exit 0 = all pass.
#   cd /c/Users/benpe/ClashBot && bash scratchpad/gauntlet/L74/deploy/overnight_dryrun.sh
cd /c/Users/benpe/ClashBot || exit 1
PY=icebow/.venv/Scripts/python.exe
D=scratchpad/gauntlet/L74/deploy
T=$(mktemp -d /tmp/ovn_dry.XXXXXX); FAILS=0
ok() { echo "  ok   $1"; }
bad() { echo "  FAIL $1"; FAILS=$((FAILS+1)); }
has() { grep -q -- "$2" "$1" && ok "$3" || bad "$3 (missing: $2)"; }
hasnt() { grep -q -- "$2" "$1" && bad "$3 (unexpected: $2)" || ok "$3"; }

# mk_summary DEST candidate|not  hard_on_ni hard_on_tornado hard_off_ni [with_old]
mk_summary() {
  mkdir -p $(dirname $1)
  { if [ $2 = candidate ]; then echo "VERDICT: candidate"; elif [ $2 = failed ]; then echo "VERDICT: FAILED (exit 1). See run.log"; else echo "VERDICT: not candidate"; fi
    echo "Nothing deployed."; echo; echo "icebow: x"
    echo "hard_on: paired n=960"; echo "  fixed-live ${HON_CI:--1.00 pp [-2.00, +0.10]}; non-inferior=$3; Tornado gate=$4"
    echo "hard_off: paired n=960"; echo "  fixed-live +0.00 pp [-1.00, +1.00]; non-inferior=$5; Tornado gate=True"
    if [ -n "$6" ]; then echo "old_on: paired n=960"; echo "  fixed-live +0 pp; non-inferior=True; Tornado gate=True"; echo "old_off: paired n=960"; echo "  fixed-live +0 pp; non-inferior=True; Tornado gate=True"; fi
  } > $1
}
# scenario NAME : sets env pieces; the caller then fills fixtures and calls run_scn
setup() {
  S=$T/$1; rm -rf $S; mkdir -p $S/{td,p3,on,live,logs,models,pod}
  echo "C:/old/live_model.pt" > $S/live/CKPT_OVERRIDE; echo 0 > $S/running
  touch $S/td/COPIED_OK
}
tornado_fixture() {   # verdict ni tornado off_ni
  local d=$S/td/x_TORNADO/results/wk/TORNADO; mk_summary $d/SUMMARY.txt $1 $2 $3 $4 old; mkdir -p $d/icebow; echo "tornado-base" > $d/icebow/fixed.pt
}
retry_fixture() {   # name verdict ni tornado off_ni
  mk_summary $S/pod/$1/SUMMARY.txt $2 $3 $4 $5; mkdir -p $S/pod/$1/icebow; echo "model-$1" > $S/pod/$1/icebow/fixed.pt
}
adapt_fixture() {   # pass|nopass|failed
  local d=$S/p3/x_ADAPT/results/wk/ADAPT; mkdir -p $d $S/p3/x_ADAPT/wk_adapt/icebow/data/bench/rl_royale/wk_adapt_main; touch $S/p3/COPIED_ADAPT
  echo "dummy" > $S/p3/x_ADAPT/wk_adapt/icebow/data/bench/rl_royale/wk_adapt_main/adaptive_final_grafted.pt
  case $1 in
    pass) printf 'VERDICT: Improvement not established. Nothing deployed.\nadaptive vs old: 960 paired games | old 50.0%% | adaptive 49.0%% | adaptive - old -1.00 pp [-2.10, +0.10]\n' > $d/SUMMARY.txt ;;
    nopass) printf 'VERDICT: Worse. Nothing deployed.\nadaptive vs old: 960 paired games | old 50.0%% | adaptive 45.0%% | adaptive - old -5.00 pp [-8.10, -3.40]\n' > $d/SUMMARY.txt ;;
    failed) printf 'VERDICT: Failed; no result established. Nothing deployed.\nExit code: 1.\n' > $d/SUMMARY.txt ;;
  esac
  if [ $1 = pass ]; then mkdir -p $S/pod/ADAPTFIX; printf 'VERDICT: built\ninit: x\nordinary_top_card_drift 0.004 epoch 3\nsmoke games 8 wins 5 draws 0 pipelined games 8\n' > $S/pod/ADAPTFIX/SUMMARY.txt; echo "model-adaptfix" > $S/pod/ADAPTFIX/adapt_fixed.pt; fi
}
run_scn() {   # extra env assignments in "$@"
  env DRY=1 POLL=1 STEP=1 GRACE=0 STALL=999 ADAPT_N=10 BK=$S TD=$S/td P3=$S/p3 ON=$S/on L=$S/live LOGS=$S/logs MODELS=$S/models \
      FAKE_POD=$S/pod FAKE_RUNNING_FILE=$S/running "$@" timeout 240 bash $D/overnight_orchestrator.sh > $S/out.txt 2>&1
  echo "  (exit $?)"
}
P() { echo "$S/on/discord_dry.log"; }

echo "== helpers selftest"; $PY $D/overnight_helpers.py selftest | grep -q PASS && ok "helpers selftest" || bad "helpers selftest"

echo "== A: TORNADO fails gate (a) -> retry r1 (2x epochs, 2x lr) passes -> deploy r1, 20-match test, ADAPT passes -> switch"
setup A; tornado_fixture not True False True; retry_fixture TORNADO_r1 candidate True True True; adapt_fixture pass
echo 1 > $S/running; (sleep 25; echo 0 > $S/running) &
run_scn
has $S/on/orchestrator.log "launch retry TORNADO_r1 \[--epochs 10 --lr 0.0002 --kl 100\]" "rule (a): 2x epochs, 2x lr"
has $(P) "TORNADO_r1 verdict: candidate" "r1 accepted"
has $(P) "stopping it between matches" "running supervisor stopped before start"
has $(P) "tornado_fix/fixed_TORNADO_r1.pt" "CKPT_OVERRIDE pointed at the r1 model"
has $(P) "Undo: cp " "undo command posted"
has $(P) "Tornado fix (TORNADO_r1), 20-match test: 20 completed ladder matches" "20-match summary"
has $(P) "54.4%" "old-model record in summary"
has $(P) "quick second-play pairs" "fast-play pair count in summary"
has $(P) "ADAPT passes" "ADAPT pass parsed"
has $(P) "ADAPT+fix model built" "ADAPT+fix copied"
has $(P) "ADAPT+fix: live model change" "switch posted"
has $S/live/CKPT_OVERRIDE "adapt_fix/adapt_fixed.pt" "CKPT_OVERRIDE now adapt_fixed"
has $S/live/CKPT_OVERRIDE.pre_adapt_backup "tornado_fix" "adapt backup = tornado model"
has $S/live/CKPT_OVERRIDE.pre_tornado_backup "C:/old/live_model.pt" "tornado backup = original"
has $(P) "ADAPT+fix (running, " "running W/L every 10 matches"
[ -e $S/on/POD5_RELEASE ] && ok "POD5_RELEASE written" || bad "POD5_RELEASE"
has $(P) "orchestrator finished" "finished"

echo "== B: gate (c) -> r1 fails gate (b) -> r2 fails -> all 3 fail, nothing deployed; ADAPT does not pass"
setup B; tornado_fixture not True True False; retry_fixture TORNADO_r1 not False True True; retry_fixture TORNADO_r2 not False True True; adapt_fixture nopass
run_scn
has $S/on/orchestrator.log "launch retry TORNADO_r1 \[--epochs 5 --lr 5e-05 --kl 200\]" "rule (c): 2x KL, half lr"
has $S/on/orchestrator.log "launch retry TORNADO_r2 \[--epochs 5 --lr 5e-05 --kl 200 --train-cell\]" "rule (b): cell head added"
has $(P) "no attempt passed" "three-failure post"
has $(P) "== TORNADO_r2" "three summaries side by side"
[ "$(cat $S/live/CKPT_OVERRIDE)" = "C:/old/live_model.pt" ] && ok "CKPT_OVERRIDE untouched" || bad "CKPT_OVERRIDE untouched"
[ -z "$(ls $S/logs)" ] && ok "live never started" || bad "live never started"
has $(P) "ADAPT did NOT pass" "ADAPT nopass post"
has $(P) "memory seeds A on pod 4 and B on pod 3" "next adaptive attempts message"

echo "== C: gate (b) first -> r1 candidate; start_live --check FAILS -> revert, nothing deployed; ADAPT failed"
setup C; tornado_fixture not False True True; retry_fixture TORNADO_r1 candidate True True True; adapt_fixture failed
run_scn FAKE_CHECK=fail
has $S/on/orchestrator.log "launch retry TORNADO_r1 \[--epochs 5 --lr 0.0001 --kl 100 --train-cell\]" "rule (b): cell head"
has $(P) "did NOT print LIVE_CHECK_PASS" "check failure posted"
[ "$(cat $S/live/CKPT_OVERRIDE)" = "C:/old/live_model.pt" ] && ok "CKPT_OVERRIDE reverted" || bad "CKPT_OVERRIDE reverted"
[ -z "$(ls $S/logs)" ] && ok "live never started" || bad "live never started"
has $(P) "ADAPT failed" "ADAPT failed post"

echo "== D: TORNADO candidate at once; live dies before 20 -> <=3 restarts then give up; ADAPT built but NOT switched"
setup D; tornado_fixture candidate True True True; adapt_fixture pass
run_scn FAKE_N=4   # 4 starts x 4 = 16 < 20, so it must give up (5 hit exactly 20 = timing flake)
has $(P) "restart 3 of 3" "3 restarts posted"
has $(P) "giving up" "gave up after 3"
has $(P) "live is broken, so it was not switched in" "ADAPT not switched when live broken"
[ "$(grep -c 'live start:' $S/on/orchestrator.log)" = 4 ] && ok "exactly 1 start + 3 restarts" || bad "start count $(grep -c 'live start:' $S/on/orchestrator.log)"

echo "== E: TORNADO FAILED (crash) -> no retry, nothing deployed"
setup E; tornado_fixture failed True True True; adapt_fixture nopass
run_scn
hasnt $S/on/orchestrator.log "launch retry" "no retry on a crash"
has $(P) "no attempt passed" "nothing deployed"

echo "== F: ORCH_STOP stops it"
setup F; rm $S/td/COPIED_OK; (sleep 3; touch $S/on/ORCH_STOP) &
run_scn
has $(P) "stopped by ORCH_STOP" "ORCH_STOP honoured"


echo "== G: all 3 Tornado attempts fail and the last one CLEARLY (wins-with-fast-plays range all below 0); ADAPT passes -> ADAPT alone, via stop + start icebow"
setup G; tornado_fixture not False True True; retry_fixture TORNADO_r1 not False True True; HON_CI="-4.00 pp [-6.00, -1.00]" retry_fixture TORNADO_r2 not False True True; adapt_fixture pass
echo 1 > $S/running; (sleep 40; echo 0 > $S/running) &
run_scn
has $S/on/orchestrator.log "clear-fail check: clear" "clear fail detected on the last attempt"
has $(P) "ADAPT alone (Tornado fix clearly failed): live model change" "ADAPT alone switched in"
has $S/live/CKPT_OVERRIDE "adapt_fix/adapt_alone.pt" "CKPT_OVERRIDE = ADAPT alone"
has $S/on/orchestrator.log "live start: ADAPT alone" "started (icebow deck), not restarted"
hasnt $(P) "ADAPT+fix: live model change" "ADAPT+fix not used"

echo "== H: all 3 fail but in the grey area (range crosses 0, Tornado gate ok); ADAPT passes -> ADAPT+fix as before, via start"
setup H; tornado_fixture not False True True; retry_fixture TORNADO_r1 not False True True; retry_fixture TORNADO_r2 not False True True; adapt_fixture pass
run_scn
has $S/on/orchestrator.log "clear-fail check: gray" "grey area detected"
has $(P) "ADAPT+fix: live model change" "ADAPT+fix switched in"
has $S/on/orchestrator.log "live start: ADAPT+fix" "ADAPT+fix started (icebow deck)"
hasnt $(P) "ADAPT alone" "ADAPT alone not used"
echo; [ $FAILS = 0 ] && echo "DRYRUN PASS ($T)" || echo "DRYRUN FAILED: $FAILS ($T)"
exit $FAILS
