# a2c9n: run9.sh's comparator/extractor env (r93 config) for single-match tools; source me
export SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=/workspace/pilot/sme8/build_snap SME_BP_FITNEXT=1 \
  SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 SME_LATE9=1 SME_MADE9=1 \
  SME_LIB=${LIB:-/workspace/pilot/lib_f635c} SME_BUILD=/workspace/pilot/sme8/build SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=/workspace/pilot/sme/repr_v2.json SME_THREADS=4 SME_CODE=${SME_CODE:-/workspace/pilot/sme9}
