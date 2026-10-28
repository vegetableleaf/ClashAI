#!/usr/bin/env bash
# loo_ext.sh TABLES_DIR LIST OUTDIR -- per-flag activation of the extractor rules: regen_fresh.sh with ONE flag set to 0 at a time
# (a copy _loo_r.sh next to it with SME_F=1 -> SME_F=0; every flag reads '0' as off). Then loo_diff.py FULL.jsonl OUTDIR.
T=$1; L=$(realpath "$2"); O=$(realpath -m "$3"); D=$(cd "$(dirname "$0")" && pwd); mkdir -p "$O"
for F in UNIT_HP IW_DEPLOY IW_AREA HERO7 OWNPLAY7 RASCAL7 GOLEM7 OWN_CAST BP_VALK BP_GK BP_GIANT BP_RASCALS BP_PRESS MECH_GB \
         MECH_DRILL MECH_HB MECH_ZAP HIDDEN GK8 CHARGE8 ZAP_ADD ZAP_POINT LATE9 MADE9 SAMETICK_ORDER IWPEND9 IWGHOST10; do
  sed "s/SME_$F=1 /SME_$F=0 /" "$D/regen_fresh.sh" > "$D/_loo_r.sh"
  grep -q "SME_$F=0 " "$D/_loo_r.sh" || { echo "flag $F not found"; exit 1; }
  bash "$D/_loo_r.sh" "$T" "$L" "$O/off_$F.jsonl" 4 > "$O/off_$F.log" 2>&1; echo off $F $(wc -l < "$O/off_$F.jsonl")
done
rm -f "$D/_loo_r.sh"
