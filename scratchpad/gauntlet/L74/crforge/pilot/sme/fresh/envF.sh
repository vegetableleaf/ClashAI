# SME-FRESH: runF.sh's env for single-match tools (source me; set SME_TABLES first or take 16.635.3)
S=/workspace/pilot/fresh/sme10f
export SME_TABLES=${SME_TABLES:-/workspace/crforge_cache/tables/16.635.3} SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 \
  SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 \
  SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 SME_LATE9=1 SME_MADE9=1 SME_LIB=/workspace/pilot/lib_f635c SME_BUILD=$S/build \
  SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=$S/repr_v2.json SME_THREADS=4 SME_CODE=$S
