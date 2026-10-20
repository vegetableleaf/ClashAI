"""L74/opp_model: every SIM promotion-style eval of the Marks with live records, as one inventory (local copies only).

Each set = (model Mark, eval context, seed block, row files).  Contexts (all gap.py arm D3, E4 grafted 430faaee opponent unless
noted, 480 paired games per seed; std = seeds 741200 + 742000, fresh = 743000 + 744000):
  rt35_live  RoyaleSim 0.1.35, live-mirrored deck pool (mix/decks_live_eval.json)       -> rt35/RT35/live_* , cues130_*
  rt35_std   RoyaleSim 0.1.35, standard CAL c pool                                      -> rt35/RT35/std_*
  f36_fact   fork36 + tower troops at live rates, factorial/successor protocol (live levels) -> pod1017_factorial/ref_*,
             pod1017_cue_ab (CXXXVIII), pod1017_successor (CLIII), codex1018 C3 same-code rerun (CLIII ref, CLIX)
  f36_tt     fork36 + troops, the 10-17 engine study (pod1017_troops LIVEEVAL_TT; u250 only)
  fin13      fork clashbot36 FIN13 parity build (stepd chain), level-11 cards / towers as before
  fin13_l16  the same with every card and tower at level 16 on both sides (EVAL_LEVELS=all16)
  s2_*       Stage-2 Phase B: f36_fact protocol with ONLY the opponent changed (E4 T .3, gen_v32_s0 d10/20/40, exploiter)
Rows give: outcome, crowns both ways, end tick, the opponent's full deck, seed / census / side (the pairing key)."""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

B = Path('C:/Users/benpe/pod_backup_weekend')
CX = B / 'codex1018/30988/20261018T181127Z/codex1018/results'
STD, FRESH = (741200, 742000), (743000, 744000)


def _g(pat):
    return sorted(glob.glob(str(B / pat)))


def _seeds(fmt, seeds):
    out = []
    for s in seeds:
        out += _g(fmt.format(s=s))
    return out


# (mark short name, context, block) -> row files.  Marks: CXII = r1, CXVII = F1 u65, CXXIV = u250, CXXXVIII = cue130,
# CLIII = succ_levels, CLIX = cue_ab2 (greedy head = the live decode), CLX = stepd_ctrl_nos2 (sampled head = the live decode).
SETS = {
    ('CXII', 'rt35_live', 'std'): _seeds('rt35/RT35/live_r1_{s}/D3/matches.jsonl', STD),
    ('CXVII', 'rt35_live', 'std'): _seeds('rt35/RT35/live_f1u65_{s}/D3/matches.jsonl', STD),
    ('CXXIV', 'rt35_live', 'std'): _seeds('rt35/RT35/live_f1u250_{s}/D3/matches.jsonl', STD),
    ('CXXXVIII', 'rt35_live', 'std'): _seeds('rt35/RT35/cues130_gae_cue_u250_{s}/D3/matches.jsonl', STD),
    ('CXII', 'rt35_std', 'std'): _seeds('rt35/RT35/std_r1_{s}/D3/matches.jsonl', STD),
    ('CXVII', 'rt35_std', 'std'): _seeds('rt35/RT35/std_f1u65_{s}/D3/matches.jsonl', STD),
    ('CXXIV', 'rt35_std', 'std'): _seeds('rt35/RT35/std_f1u250_{s}/D3/matches.jsonl', STD),
    ('CXXIV', 'f36_fact', 'std'): _seeds('pod1017_factorial/ref_u250/eval/ref_u250_{s}/D3/matches.jsonl', STD),
    ('CXXXVIII', 'f36_fact', 'std'): _seeds('pod1017_factorial/ref_cxxxviii/eval/ref_cxxxviii_{s}/D3/matches.jsonl', STD),
    ('CXXXVIII', 'f36_fact', 'fresh'): _seeds('pod1017_successor/fresh_ref_cxxxviii/eval/fresh_ref_cxxxviii_{s}/D3/matches.jsonl', FRESH),
    ('CLIII', 'f36_fact', 'std'): [str(CX / f'clIII_ref_{s}/D3/matches.jsonl') for s in STD],
    ('CLIII', 'f36_fact', 'fresh'): [str(CX / f'clIII_ref_{s}/D3/matches.jsonl') for s in FRESH],
    ('CLIX', 'f36_fact', 'std'): [str(CX / f'cue_ab2_{s}/D3/matches.jsonl') for s in STD],
    ('CLIX', 'f36_fact', 'fresh'): [str(CX / f'cue_ab2_{s}/D3/matches.jsonl') for s in FRESH],
    ('CLIX_sample', 'f36_fact', 'std'): [str(CX / f'cue_ab2_sample_{s}/D3/matches.jsonl') for s in STD],
    ('CLIX_sample', 'f36_fact', 'fresh'): [str(CX / f'cue_ab2_sample_{s}/D3/matches.jsonl') for s in FRESH],
    ('CXXIV', 'f36_tt', 'std'): _seeds('pod1017_troops/LIVEEVAL_TT/tt_u250_{s}/D3/matches.jsonl', STD),
    ('CLIII', 'fin13', 'std'): _seeds('stepd/clIII_fin13/eval/clIII_fin13_{s}_fin13/D3/matches.jsonl', STD),
    ('CLIII', 'fin13', 'fresh'): _seeds('stepd/clIII_fin13/eval/clIII_fin13_{s}_fin13/D3/matches.jsonl', FRESH),
    ('CLX', 'fin13', 'std'): _seeds('stepd/stepd_ctrl_nos2/eval/stepd_ctrl_nos2_{s}_fin13/D3/matches.jsonl', STD),
    ('CLX', 'fin13', 'fresh'): _seeds('stepd/stepd_ctrl_nos2/eval/stepd_ctrl_nos2_{s}_fin13/D3/matches.jsonl', FRESH),
    ('CTRL', 'fin13', 'std'): _seeds('stepd/stepd_ctrl/eval/stepd_ctrl_{s}_fin13/D3/matches.jsonl', STD),
    ('CTRL', 'fin13', 'fresh'): _seeds('stepd/stepd_ctrl/eval/stepd_ctrl_{s}_fin13/D3/matches.jsonl', FRESH),
    ('CLIII', 'fin13_l16', 'std'): _seeds('stepd/cliii_l16/eval/cliii_l16_{s}_fin13/D3/matches.jsonl', STD),
    ('CLIII', 'fin13_l16', 'fresh'): _seeds('stepd/cliii_l16/eval/cliii_l16_{s}_fin13/D3/matches.jsonl', FRESH),
    ('CLX', 'fin13_l16', 'std'): _seeds('stepd/clx_l16/eval/clx_l16_{s}_fin13/D3/matches.jsonl', STD),
    ('CLX', 'fin13_l16', 'fresh'): _seeds('stepd/clx_l16/eval/clx_l16_{s}_fin13/D3/matches.jsonl', FRESH),
}
for _job, _ctx in (('B1_e4T3', 's2_e4T3'), ('B2_gen10', 's2_gen10'), ('B3_gen20', 's2_gen20'), ('B4_gen40', 's2_gen40'),
                   ('B5_expl', 's2_expl')):
    for _m in ('CXXIV', 'CXXXVIII'):
        SETS[(_m, _ctx, 'std')] = _seeds(f'stage2/{_job}_{_m}/{_job}_{_m}_{{s}}/D3/matches.jsonl', STD)

for _m, _ctx, _pat in (('CXII', 'tel_cal_e4', 'pod1014b_econ/ECON_r1/g_{s}/D3/matches.jsonl'),
                       ('CXXIV', 'tel_hog_e4', 'stage2/T_e4base/T_e4base_{s}/D3/matches.jsonl'),
                       ('CXXIV', 'tel_hog_il65', 'stage2/T_il_u0065/T_il_u0065_{s}/D3/matches.jsonl'),
                       ('CXXIV', 'tel_hog_e4u65', 'stage2/T_e4_u0065/T_e4_u0065_{s}/D3/matches.jsonl'),
                       ('CXXXVIII', 'c_hog13k_il65', 'stage2/C_il_u0065_13k/C_il_u0065_13k_{s}/D3/matches.jsonl'),
                       ('CXXXVIII', 'c_hog13k_e4u65', 'stage2/C_e4_u0065_13k/C_e4_u0065_13k_{s}/D3/matches.jsonl')):
    SETS[(_m, _ctx, 'std')] = _seeds(_pat, STD)


def tel_falls(j):
    """Exact tower falls (clock ticks) from the behaviour telemetry's lr_frames (towers every ~10 ticks), learner = 'own';
    keys as live_table.py: own_K / own_P<n> / opp_K / opp_P<n>.  None when the row has no telemetry."""
    fr = ((j.get('behaviour') or {}).get('lr_frames'))
    if not fr:
        return None
    me = int(j['learner_side'])
    ser, ticks = {}, []
    for t, _el, _bodies, towers in fr:
        ticks.append(int(t))
        for side, kind, x, y, hp in towers:
            ser.setdefault((int(side), kind, round(x)), {})[int(t)] = hp or 0
    falls = {}
    for (side, kind, x), s in ser.items():
        name = ('own' if side == me else 'opp') + '_' + ('K' if kind == 'king' else 'P%d' % x)
        alive = [t for t, hp in s.items() if hp > 0]
        if alive and max(alive) < ticks[-1]:
            falls[name] = next(t for t in ticks if t > max(alive))
        elif not alive:
            falls[name] = ticks[0]
    # a tower that is simply ABSENT from the last frames (destroyed towers drop out of the list) also fell
    last = {(int(side), kind, round(x)) for side, kind, x, y, hp in fr[-1][3]}
    for key, s in ser.items():
        name = ('own' if key[0] == me else 'opp') + '_' + ('K' if key[1] == 'king' else 'P%d' % key[2])
        if key not in last and name not in falls:
            falls[name] = next(t for t in ticks if t > max(s))
    # the match-ending crown lands after the last 10-tick frame: add it from the final crowns, at the end tick, on the
    # weakest standing tower(s) of that side (king when the side lost 3 crowns)
    for who, final in (('opp', j['crowns_for']), ('own', j['crowns_against'])):
        have = 3 if who + '_K' in falls else sum(k.startswith(who + '_P') for k in falls)
        if final == 3 and who + '_K' not in falls:
            falls[who + '_K'] = int(j['end_tick'])
        elif final > have:
            standing = sorted((hp, ('own' if side == me else 'opp') + '_P%d' % round(x)) for side, kind, x, y, hp in fr[-1][3]
                              if kind == 'princess' and (('own' if side == me else 'opp') == who))
            for _, name in standing[:final - have]:
                falls[name] = int(j['end_tick'])
    return falls


KEEP = ('outcome', 'crowns_for', 'crowns_against', 'end_tick', 'opp_deck', 'seed', 'census', 'learner_side', 'opp_deck_name',
        'opp_plays_accepted', 'plays_accepted', 'tower_hp_for', 'tower_hp_against')


def rows(key):
    """Rows of one set; an aggregate D3/matches.jsonl only (never its 0000x shard copies)."""
    out = []
    for f in SETS[key]:
        if not Path(f).exists():
            continue
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            r = {k: j.get(k) for k in KEEP}
            r['falls'] = tel_falls(j)
            out.append(r)
    return out


def pair_key(r):
    return (r['seed'], r['census'], r['learner_side'], r['opp_deck_name'])


def paired(ra, rb):
    """Paired win-rate difference a - b over the games both sets share (same seed / census / side / deck);
    normal 95% CI on the mean paired difference (draws = non-wins, as every promotion readout)."""
    ib = {pair_key(r): r for r in rb}
    d = [(r['outcome'] == 'win') - (ib[pair_key(r)]['outcome'] == 'win') for r in ra if pair_key(r) in ib]
    n = len(d)
    if n < 30:
        return None
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    h = 1.96 * sd / math.sqrt(n)
    return m, m - h, m + h, n


if __name__ == '__main__':
    for k in SETS:
        R = rows(k)
        w = sum(r['outcome'] == 'win' for r in R)
        print(k, len(SETS[k]), 'files', len(R), 'rows', f'{w}/{len(R)}' if R else '-')
