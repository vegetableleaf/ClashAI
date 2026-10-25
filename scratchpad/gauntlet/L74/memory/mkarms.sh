#!/bin/bash
# mkarms.sh INIT -- pod-side, in the training tree: write tonight's memory arm cfgs from CLXIII's recipe (succ48_o_s91.yaml),
# Plan A redesign 10-25 night. INIT = the S3-aux checkpoint (repo-relative path: drift_test prefixes $CB).
# Common to every arm: memory v2 + memory_aux v1 + memory_encoder_frozen (coupling zero = CLXIII at u0), seed per arm, 100 updates
# (gated at u100, owner 10-25), critic scale 3.5 (>= 1 + habit + crown bounds; the trainer refuses a short one), and the owner's
# S4 exploiter POOL (league_exploiters list): D1 deny (live-like X-Bow denial: lock 0.544, 8% shut-outs vs live CLX 0.565 / 9%)
# + calibrated I u40 + W18 R3, each on the live decks with fast counter decks x3 (mix/decks_live_train_cx3.json), at their
# measured calibrated decode (T .1, decide 20, tau .2); 40% of training games (CLXIII's recipe: 30% vs I u40 alone).
#   mem_a_s106    memory only                                         (attribution)
#   mem_e_s106    + habit_xbow_w 0.1 + rocket_cycle + king_redirect   (the candidate)
#   mem_e_s107    the candidate, second seed
#   mem_l_s106    + rocket_cycle + king_redirect (no failed-X-Bow cost: it leaked without memory on 10-25)
set -euo pipefail
INIT=$1
C=scratchpad/gauntlet/L74/stepd/cfg; B=$C/succ48_o_s91.yaml; O=icebow/data/pipeline/o2
[ -f "$INIT" ] || { echo "no $INIT"; exit 2; }
for f in $O/w14opp_I.pt $O/oppD1_deny_s74_u0060.pt $O/oppW18R3_playcost_s74_u0040.pt scratchpad/gauntlet/L74/mix/decks_live_train_cx3.json; do
  [ -f $f ] || { echo "missing $f"; exit 2; }; done
X="decks: scratchpad/gauntlet/L74/mix/decks_live_train_cx3.json, T: 0.1, decide_every: 20, tau: 0.2"
base() {   # $1 name, $2 seed
  sed -e "s#^init: .*#init: $INIT#" -e "s/^seed: 91/seed: $2/" -e "s/^max_updates: 300/max_updates: 100/" \
      -e "s/^shaping_critic_scale: 2.2/shaping_critic_scale: 3.5/" -e "/^league_exploiters:/,/^  tau: 0.2/d" \
      -e "1i # Plan A redesign arm $1 (10-25 night; memory/mkarms.sh): CLXIII recipe + memory v2 + aux-pretrained frozen encoder." $B
  printf '%s\n' "memory: v2" "memory_aux: v1" "memory_encoder_frozen: true" "league_exploiters:" \
    "- {ckpt: $O/w14opp_I.pt, share: 0.15, $X}" "- {ckpt: $O/oppD1_deny_s74_u0060.pt, share: 0.15, $X}" \
    "- {ckpt: $O/oppW18R3_playcost_s74_u0040.pt, share: 0.10, $X}"
}
base mem_a_s106 106 > $C/mem_a_s106.yaml
for a in "mem_e_s106 106" "mem_e_s107 107"; do set -- $a
  { base $1 $2; printf '%s\n' "habit_xbow_w: 0.1" "rocket_cycle: true" "king_redirect: true"; } > $C/$1.yaml; done
{ base mem_l_s106 106; printf '%s\n' "rocket_cycle: true" "king_redirect: true"; } > $C/mem_l_s106.yaml
for f in mem_a_s106 mem_e_s106 mem_e_s107 mem_l_s106; do
  [ "$(grep -c '^league_exploiters:' $C/$f.yaml)" = 1 ] || { echo "$f: league_exploiters block not replaced"; exit 3; }
  echo "== $f: $(grep -E '^(init|seed|max_updates|shaping_critic_scale|memory|memory_aux|memory_encoder_frozen|habit_xbow_w|rocket_cycle|king_redirect):' $C/$f.yaml | tr '\n' ' ')"
done
