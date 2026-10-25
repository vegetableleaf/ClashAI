#!/bin/bash
# mkarms.sh INIT [EXPLOITER_CKPT] -- pod-side, in the training tree: write tonight's memory arm cfgs from CLXIII's recipe
# (succ48_o_s91.yaml), Plan A redesign 10-25 night. INIT = the S3-aux checkpoint (repo-relative path: drift_test prefixes $CB).
# Common to every arm: memory v2 + memory_aux v1 + memory_encoder_frozen (coupling zero = CLXIII at u0), seed per arm, 100 updates
# (gate at u75), critic scale 3.5 (>= 1 + habit + crown bounds; the trainer refuses a short one), exploiter decks with fast
# counter decks x3 (mix/decks_live_train_cx3.json), optional exploiter checkpoint swap (D1 if its X-Bow-denial check passes).
#   mem_a_s106    memory only                                         (attribution)
#   mem_e_s106    + habit_xbow_w 0.1 + rocket_cycle + king_redirect   (the candidate)
#   mem_e_s107    the candidate, second seed
#   mem_l_s106    + rocket_cycle + king_redirect (no failed-X-Bow cost: it leaked without memory on 10-25)
set -euo pipefail
INIT=$1; EXP=${2:-}
C=scratchpad/gauntlet/L74/stepd/cfg; B=$C/succ48_o_s91.yaml
[ -f "$INIT" ] || { echo "no $INIT"; exit 2; }
base() {   # $1 name, $2 seed
  sed -e "s#^init: .*#init: $INIT#" -e "s/^seed: 91/seed: $2/" -e "s/^max_updates: 300/max_updates: 100/" \
      -e "s/^shaping_critic_scale: 2.2/shaping_critic_scale: 3.5/" \
      -e "s#^  decks: scratchpad/gauntlet/L74/mix/decks_live_train.json#  decks: scratchpad/gauntlet/L74/mix/decks_live_train_cx3.json#" \
      -e "1i # Plan A redesign arm $1 (10-25 night; memory/mkarms.sh): CLXIII recipe + memory v2 + aux-pretrained frozen encoder." $B
  [ -n "$EXP" ] && echo "# exploiter swapped by mkarms.sh: $EXP"
  printf '%s\n' "memory: v2" "memory_aux: v1" "memory_encoder_frozen: true"
}
base mem_a_s106 106 > $C/mem_a_s106.yaml
for a in "mem_e_s106 106" "mem_e_s107 107"; do set -- $a
  { base $1 $2; printf '%s\n' "habit_xbow_w: 0.1" "rocket_cycle: true" "king_redirect: true"; } > $C/$1.yaml; done
{ base mem_l_s106 106; printf '%s\n' "rocket_cycle: true" "king_redirect: true"; } > $C/mem_l_s106.yaml
if [ -n "$EXP" ]; then
  for f in mem_a_s106 mem_e_s106 mem_e_s107 mem_l_s106; do sed -i "s#^  ckpt: icebow/data/pipeline/o2/w14opp_I.pt#  ckpt: $EXP#" $C/$f.yaml; done
fi
for f in mem_a_s106 mem_e_s106 mem_e_s107 mem_l_s106; do
  echo "== $f: $(grep -cE '^(memory|memory_aux|memory_encoder_frozen|habit_xbow_w|rocket_cycle|king_redirect):' $C/$f.yaml) keys; \
$(grep -E '^(init|seed|max_updates|shaping_critic_scale):|^  (ckpt|decks):' $C/$f.yaml | tr '\n' ' ')"
done
