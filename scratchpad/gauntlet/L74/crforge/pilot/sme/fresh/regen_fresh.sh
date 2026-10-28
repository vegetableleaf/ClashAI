#!/usr/bin/env bash
# usage: regen_fresh.sh TABLES_DIR LIST OUT.jsonl -- inputs_v29's extractor flag set exactly:
#   a2c9z/regen9z.sh's 20 flags + a2c9n/regen9n.sh's ZAP_ADD ZAP_POINT LATE9 MADE9 + v29's SAMETICK_ORDER IWPEND9 IWGHOST10
# (SME.md A2c-10: v29 = regen9n.sh OUT SME_SAMETICK_ORDER=1 SME_IWPEND9=1 SME_IWGHOST10=1), via regen_fresh.py's table swap.
cd "$(dirname "$0")" && env SME_UNIT_HP=1 SME_IW_DEPLOY=1 SME_IW_AREA=1 SME_HERO7=1 SME_OWNPLAY7=1 SME_RASCAL7=1 SME_GOLEM7=1 \
  SME_OWN_CAST=1 SME_BP_VALK=1 SME_BP_GK=1 SME_BP_GIANT=1 SME_BP_RASCALS=1 SME_BP_PRESS=1 SME_MECH_GB=1 SME_MECH_DRILL=1 \
  SME_MECH_HB=1 SME_MECH_ZAP=1 SME_HIDDEN=1 SME_GK8=1 SME_CHARGE8=1 \
  SME_ZAP_ADD=1 SME_ZAP_POINT=1 SME_LATE9=1 SME_MADE9=1 SME_SAMETICK_ORDER=1 SME_IWPEND9=1 SME_IWGHOST10=1 \
  /c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -I regen_fresh.py "$1" "$2" "$3" ${4:-4}
