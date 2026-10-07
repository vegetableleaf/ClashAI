"""L73 live wiring, Part A: load R1e (fv4), an fv5 and the fv6 smoke checkpoint through the LIVE loading path
(live_play.load_pilot -> pipeline.live_gen_v2.GenPilot, the live supervisor's entry) and replay RECORDED reader v2
frames (live_play's loop order: observe() every active+coherent one-hand frame, decide() from tick 150). Checks:
  fv5 identity path (from_engine feature_version, card_id -1 body forwarding, Hero Ice Wizard dedupe),
  projectiles reaching the fv6 target-patch branch, CPU decision latency (pilots interleaved per frame).
Inputs (read-only, main checkout): the 3 checkpoints; sidebyside/re_v2xb.jsonl (10-03, 975 frames) and
reader_character_identity/passive_v2_raw.jsonl (10-06, 120 frames). Run via decode_options/lowprio.py (CPU, 4 threads).
Writes results_partA.json next to this file."""
import argparse, copy, itertools, json, os, statistics, sys, time
from pathlib import Path
import numpy as np, torch

HERE = Path(__file__).resolve().parent
WT = HERE.parents[3]
sys.path[:0] = [str(WT), str(WT / 'scratchpad/gauntlet/L68/live_reader')]
import live_play  # noqa: E402  the live entry (its load_pilot is the live loading path)
from pipeline import obs_contract, live_mem  # noqa: E402
from pipeline import public_observation as PO  # noqa: E402
from pipeline.decision_options import add_arguments, config_from_args, phase_index, is_xbow  # noqa: E402
from pipeline.reader_identity_aliases import HERO_ICE_WIZARD_ID  # noqa: E402

MAIN = Path('C:/Users/benpe/ClashBot')
CKPTS = {'R1e_fv4': MAIN / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt',
         'fv5': MAIN / 'icebow/data/bench/development_iteration_1_20261005/ordinary_v5/candidate_portable.pt',
         'fv6_smoke': MAIN / 'scratchpad/gauntlet/L73/barrel_branch/smoke/gen_branch_s0.pt'}
FRAMES = [MAIN / 'scratchpad/gauntlet/L70/reader/sidebyside/re_v2xb.jsonl',
          MAIN / 'scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/passive_v2_raw.jsonl']


def frames(path):
    for line in open(path, encoding='utf-8'):
        try:
            f = json.loads(line)
        except ValueError:
            continue
        if f.get('battle_active') and f.get('coherent') and \
                len([p for p in f['players'] if any(i >= 0 for i in p['hand_deck_indices'])]) == 1:
            yield f


def hero_dupes(ents):
    """same-side Hero Ice Wizard objects within 500 reader units of an earlier one (what dedupe_hero_bodies drops)."""
    h = [e for e in ents if int(e.get('card_id', -1)) == HERO_ICE_WIZARD_ID]
    return sum(any(k['side'] == e['side'] and abs(k['x'] - e['x']) <= 500 and abs(k['y'] - e['y']) <= 500
                   for k in h[:i]) for i, e in enumerate(h))


def load(name, options=()):
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    cfg = config_from_args(ap.parse_args(list(options)))
    a = argparse.Namespace(ckpt=str(CKPTS[name]), device='cpu', tau=0.35, no_opp_counter=False, extrapolate=26,
                           decision_seed=cfg['decision_seed'], public_audit=True)
    return live_play.load_pilot(a, cfg)[1]


def main():
    pilots = {k: load(k) for k in CKPTS}
    pilots['fv6_smoke+options'] = load('fv6_smoke', ['--tau-phase', '0.35', '0.45', '0.55',
                                                     '--xbow-class', 'class_sample', '--xbow-class-floor', '0.3'])
    cur = {'name': None}
    stat = {k: dict(fe_fv=set(), fe_calls=0, toobs_dupes=0, observe_dupes=0, branch_calls=0, branch_rows_with_proj=0,
                    raw_proj_frames=0, ms=[], plays=0, errors={}, plays_below_phase_tau=0, xbow_plays=0,
                    last_calls=[], dec_raw_proj=0, dec_raw_named_proj=0, dec_model_proj=0, dec_model_target_proj=0, dec_branch_valid=0, dec_branch_match=0) for k in pilots}
    orig_fe, orig_to, orig_upd = obs_contract.from_engine, live_mem.to_observe, PO.PublicObserver.update

    def fe(*a, **k):
        s = stat[cur['name']]; s['fe_fv'].add(k.get('feature_version', 1)); s['fe_calls'] += 1
        return orig_fe(*a, **k)

    def to(frame, *a, **k):
        stat[cur['name']]['toobs_dupes'] += hero_dupes(frame['entities'])
        return orig_to(frame, *a, **k)

    def upd(self, frame, *a, **k):
        stat[cur['name']]['observe_dupes'] += hero_dupes(frame.get('entities') or [])
        return orig_upd(self, frame, *a, **k)
    obs_contract.from_engine, live_mem.to_observe, PO.PublicObserver.update = fe, to, upd

    branch = {}
    for name, p in pilots.items():
        if p.feature_version >= 6:
            orig_tp = p.model.target_patches

            def tp(b, _orig=orig_tp, _name=name):
                obj = b['projectiles']; xy = obj[..., 4:6]
                valid = (obj[..., 0] > 0) & (xy >= 0).all(-1) & (xy <= 1).all(-1)
                out = _orig(b)
                s = stat[_name]; s['branch_calls'] += 1
                s['branch_rows_with_proj'] += int(valid.any())
                s['last_calls'].append(int(valid.sum()))
                branch.setdefault(_name, []).append(float(out.abs().sum()))
                return out
            p.model.target_patches = tp
    raw_hero_dupes = n_frames = raw_proj = 0
    for path in FRAMES:
        for p in pilots.values():
            p.reset_match()
        for f in itertools.islice(frames(path), int(os.environ.get('MAXF', 10**9))):
            n_frames += 1
            raw_hero_dupes += hero_dupes(f['entities'])
            raw_proj += bool(f.get('projectiles'))
            for name, p in pilots.items():
                cur['name'] = name
                p.observe(f)
                if int(f['game_tick']) < live_play.UI_READY_MIN_TICK:
                    continue
                t = time.perf_counter()
                try:
                    d = p.decide(f)
                except ValueError as exc:
                    stat[name]['errors'][str(exc)] = stat[name]['errors'].get(str(exc), 0) + 1
                    continue
                stat[name]['ms'].append((time.perf_counter() - t) * 1000)
                stat[name]['plays'] += bool(d['play'])
                taus = p.decision_options.tau_phase
                if taus and d['play'] and d['p_play'] <= taus[int(phase_index(d['bs'].t_sec))]:
                    stat[name]['plays_below_phase_tau'] += 1
                if d.get('name') and is_xbow(d['name']) and d['play']:
                    stat[name]['xbow_plays'] += 1
                stat[name]['raw_proj_frames'] += bool(f.get('projectiles'))
                s, au = stat[name], d.get('public_audit') or {}
                mp = au.get('model_projectiles', [])
                tgt = sum(0 <= r[4] <= 1 and 0 <= r[5] <= 1 for r in mp)
                s['dec_raw_proj'] += bool(au.get('raw_projectiles'))
                s['dec_raw_named_proj'] += any(int(r.get('card_id', -1)) >= 0 for r in au.get('raw_projectiles', []))
                s['dec_model_proj'] += bool(mp)
                s['dec_model_target_proj'] += bool(tgt)
                if p.feature_version >= 6:
                    first = s['last_calls'][0] if s['last_calls'] else -1
                    s['dec_branch_valid'] += first > 0
                    s['dec_branch_match'] += first == tgt
                s['last_calls'].clear()
    obs_contract.from_engine, live_mem.to_observe, PO.PublicObserver.update = orig_fe, orig_to, orig_upd

    # card_id -1 troop injection (no recorded frame carries one): a level-15 cursed hog (915 HP, opponent side 0)
    f0 = next(frames(FRAMES[0]))
    inj = copy.deepcopy(f0)
    inj['entities'].append({'address': '0xdead', 'category': 5000999, 'kind': 15, 'side': 0, 'x': 9000, 'y': 14000,
                            'card_id': -1, 'level': 15, 'hp': 915, 'max_hp': 915, 'behavior_state_raw': 0, 'evo': 0})
    injected = {}
    for name in CKPTS:
        p = load(name)
        p.observe(inj)
        _, info = p.row(inj)
        injected[name] = [obs_contract.vocab.UNIT_VOCAB[u.cls] for u in info['bs'].units
                          if u.side == 1 and abs(u.x - 0.5) < 1e-3 and abs(u.y - 0.4375) < 1e-3]
    out = dict(frames=n_frames, raw_frames_with_projectiles=raw_proj, raw_hero_duplicate_objects=raw_hero_dupes,
               injected_cursed_hog_opponent_units_at_x_0_5=injected, checkpoints={})
    for name, s in stat.items():
        ms = np.array(s['ms'])
        out['checkpoints'][name] = dict(
            feature_version=pilots[name].feature_version, from_engine_feature_versions=sorted(s['fe_fv']),
            from_engine_calls=s['fe_calls'], hero_dupes_reaching_to_observe=s['toobs_dupes'],
            hero_dupes_reaching_public_observer=s['observe_dupes'], decisions=len(ms), plays=s['plays'], errors=s['errors'], xbow_plays=s['xbow_plays'],
            plays_with_p_at_or_below_phase_tau=s['plays_below_phase_tau'],
            latency_ms=dict(median=round(float(np.median(ms)), 1), p95=round(float(np.percentile(ms, 95)), 1),
                            max=round(float(ms.max()), 1), mean=round(float(ms.mean()), 1)),
            decisions_with_raw_projectiles=s['dec_raw_proj'], decisions_with_raw_named_projectiles=s['dec_raw_named_proj'], decisions_with_model_projectile_tokens=s['dec_model_proj'],
            decisions_with_known_target_tokens=s['dec_model_target_proj'],
            decisions_branch_saw_valid_projectiles=s['dec_branch_valid'],
            decisions_branch_valid_count_equals_known_target_tokens=s['dec_branch_match'],
            branch_calls=s['branch_calls'], branch_rows_with_valid_projectiles=s['branch_rows_with_proj'],
            decided_frames_with_raw_projectiles=s['raw_proj_frames'],
            branch_output_abs_sum_nonzero=sum(v > 0 for v in branch.get(name, [])),
            spread_weight_abs_sum=(float(pilots[name].model.projectile_target_spread.weight.detach().abs().sum())
                                   if pilots[name].feature_version >= 6 else None))
    (HERE / (sys.argv[1] if len(sys.argv) > 1 else 'results_partA.json')).write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
