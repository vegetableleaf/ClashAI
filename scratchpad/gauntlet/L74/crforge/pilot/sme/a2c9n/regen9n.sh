#!/usr/bin/env bash
# usage: regen9n.sh OUT.jsonl [VAR=1 ...] -- inputs_v27's flag set (9Z: ZAP_ADD/ZAP_POINT, 9T: LATE9/MADE9) plus extras
#   v27  = regen9n.sh OUT                          (157e183a)
#   v27o = regen9n.sh OUT SME_SAMETICK_ORDER=1     (ab3c7114, A2c-9R's order_inputs pass)
OUT=$1; shift
exec bash "$(dirname "$0")/../a2c9z/regen9z.sh" "$OUT" SME_ZAP_ADD=1 SME_ZAP_POINT=1 SME_LATE9=1 SME_MADE9=1 "$@"
