#!/bin/bash
# 10-14 afternoon, 3 owner pods. After pod_setup_l74.sh (repo.tgz = current main without L67/L72/templates/webcache):
#   nohup bash /workspace/in/pod1014b.sh stage > /dev/null 2>&1 &        -> /workspace/STAGE_OK
#   nohup bash /workspace/in/pod1014b.sh econ|distill_adapt|twin > /dev/null 2>&1 &
# econ          = r1's elixir at push start in the SIM (L74/econ2/econ_r1_pod.sh), ~1.2 h
# distill_adapt = step 4 on ADAPT (owner 10-14): teacher = ADAPT + OLD's grafted heads (exactly as the 47.08% row of
#                 rltest/FINDING.md), student = plain ADAPT; run_distill.sh smoke, then all (~3 h)
# twin          = the A/B3 SIM twin: r1 full graft D3 with the live press rule (= the 402/960 rows) vs never pressed
set -Eeuo pipefail
CB=/workspace/clashbot; IN=/workspace/in; PY=/workspace/venv33/bin/python; R=/workspace/results
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
cd $CB
export UV_HTTP_TIMEOUT=600 PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
mkdir -p $R
case $1 in
stage)
  exec >> /workspace/stage.log 2>&1
  trap 'echo "STAGE FAILED line $LINENO"; touch /workspace/STAGE_FAILED' ERR
  [ -e $IN/data_rl.tgz ] && { tar xzf $IN/data_rl.tgz --no-same-owner -C $CB && sha256sum -c --quiet $IN/data.sha && echo DATA_OK; }
  tar xzf $IN/rsdata.tgz --no-same-owner -C $CB && sha256sum -c --quiet $IN/rsdata.sha && echo RSDATA_OK
  tar xzf $IN/ckpts.tgz --no-same-owner -C $CB && sha256sum -c $IN/ckpts.sha
  $PY -c "import torch" 2>/dev/null || uv pip install -q -p $PY --reinstall-package torch torch --index-url https://download.pytorch.org/whl/cu128
  $PY -c "import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0))"
  $PY -c "from pipeline.royale_runtime import activate; print(activate()['runtime_id'])"
  echo "cpu quota: $(cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null | tr "
" " " || true)"
  touch /workspace/STAGE_OK ;;
econ)
  exec >> $R/econ.log 2>&1
  bash scratchpad/gauntlet/L74/econ2/econ_r1_pod.sh && touch $R/ECON_OK || touch $R/ECON_FAILED ;;
distill_adapt)
  exec >> $R/distill_adapt.log 2>&1
  T=$RL/wk_adapt_main/wk_adapt_main_latest_grafted.pt
  [ -f $T ] || $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $RL/wk_adapt_main/wk_adapt_main_latest.pt $OLD $T
  sha256sum $RL/wk_adapt_main/wk_adapt_main_latest.pt $T
  export TEACHER=$T STUDENT=$RL/wk_adapt_main/wk_adapt_main_latest.pt OUT=$RL/distill/distill_adapt_d3.pt R=$R/DISTILL_ADAPT
  bash scratchpad/gauntlet/L74/distill/run_distill.sh smoke && bash scratchpad/gauntlet/L74/distill/run_distill.sh all \
    && touch $R/DISTILL_ADAPT_OK || touch $R/DISTILL_ADAPT_FAILED ;;
twin)
  exec >> $R/twin.log 2>&1
  CK=$RL/newsim_r1/newsim_base_r1_final_grafted.pt
  for P in live never; do for S in 741200 742000; do
    flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $R/TWIN_${P}_$S --arms D3 \
      --iw-press $P --workers ${WORKERS:-13} --seed-start $S > $R/TWIN_${P}_$S.log 2>&1 || echo "FAILED $P $S"
    grep -E "^D3:" $R/TWIN_${P}_$S/SUMMARY.txt || true
  done; done
  touch $R/TWIN_DONE ;;
rlarm_gae|rlarm_opp|rlarm_gae_opp|rlarm_gae_tg|rlarm_gae_opp_tg|rlarm_kl_imit|rlarm_gae_solv|rlarm_gae_tower)   # REWARD_ARCHITECTURE.md steps 1-3 (F1 per-decision credit / F3 decisive opponents / F6 KL_gate to imitation / step 3 = gae + ONE potential: A2 solvency, A1+A1b tower_score), one change each
  exec bash scratchpad/gauntlet/L74/rlarms/run_rlarm.sh ${1#rlarm_} ;;
audit_a1a2)   # step-3 pre-flight 9.1-9.3 on SIM rollouts (L74/reward/preflight_a1a2.py audit): IL (gen_v1_s0) + r1 policies
  exec >> $R/audit_a1a2.log 2>&1
  for CK in icebow/data/pipeline/gen_v1_s0/gen_s0.pt $RL/newsim_r1/newsim_base_r1_final_grafted.pt; do
    N=$(basename $(dirname $CK))
    flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/reward/preflight_a1a2.py audit --out $R/AUDIT_A1A2_$N \
      --ckpt $CK --matches ${MATCHES:-100} --workers ${WORKERS:-13} || echo "AUDIT EXIT $? $N"
  done
  touch $R/AUDIT_A1A2_DONE ;;
esac
