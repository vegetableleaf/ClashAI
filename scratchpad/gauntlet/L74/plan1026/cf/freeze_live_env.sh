#!/usr/bin/env bash
# fl_env.sh CMD... : envR.sh's gate env on /workspace/smeR6 with SME_TABLES = $TAB (a perturbed copy), CPUs 226-237
R=${R:-/workspace/smeR6}; S=$R/sme; T=${TAB:-/workspace/crforge_cache/tables/16.635.3}
export NPY_DISABLE_CPU_FEATURES=X86_V4,AVX512_ICL OPENBLAS_CORETYPE=ZEN
cd $S && exec env SME_TABLES=$T SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 \
  SME_LATE9=1 SME_MADE9=1 SME_LIB=/workspace/crforge_main/5e8089a4/tickprobe/lib SME_BUILD=$S/build SME_HP_PLACEHOLDER=1 \
  SME_TORN_CMD=1 SME_REPR=$S/repr_v2.json SME_THREADS=${SME_THREADS:-4} SME_HIDDEN_ASSIGN=1 SME_CLS_TICKS=1 \
  SME_BANNER_GIVEN=1 taskset -c ${CPUS:-226-237} "$@"
