#!/bin/bash
# Off byte-identical: the SAME SIM matches on MAIN (tree tmain) and on this branch with the rule OFF (default flags), and with the rule
# ON but never triggering (--rocket-value 99), deployed bundle, 12 seeds of the EVO census; per-match rows compared field by field.
#   bash vm_parity.sh TREE_NEW TREE_MAIN
N=$1; M=$2; O=~/rocket_value2/parity; rm -rf $O; mkdir -p $O
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel
    --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --behaviour-telemetry)
run() { local tree=$1 name=$2; shift 2
  ( cd ~/rocket_value2/$tree && nice -n 10 $PY -m pipeline.search_s0 --out $O/$name --seeds 0:12 --opps gen --arms plain --gen $CK \
      --opp-gen $GEN1 --forms-mode deck --device cpu --workers 4 --tail-cap 7200 --tau-plain 0.35 --census $EVO --hero-abilities \
      --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" "$@" > $O/$name.log 2>&1 ); }
run $M main &
run $N off &
run $N noop --rocket-value 99 &
wait
$PY - <<'EOF'
import json, os
O = os.path.expanduser('~/rocket_value2/parity')
def rows(n):
    out = {}
    for l in open(f'{O}/{n}/matches.jsonl'):
        r = json.loads(l)
        if r.get('arm') == 'plain':
            r.pop('wall_s', None); out[r['tag']] = r
    return out
m = rows('main')
for n in ('off', 'noop'):
    r = rows(n)
    keys = ('outcome', 'crowns_for', 'crowns_against', 'tower_hp_for', 'tower_hp_against', 'end_tick', 'plays_accepted', 'plays_attempted', 'decisions', 'opp_plays_accepted')
    bad = [t for t in m if t not in r or any(m[t].get(k) != r[t].get(k) for k in keys)]
    print(f'{n}: {len(r)} matches vs main {len(m)}; differing on {keys}: {len(bad)} {bad[:5]}')
EOF
