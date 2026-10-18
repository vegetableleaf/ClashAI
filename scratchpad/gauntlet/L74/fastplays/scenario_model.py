"""L74 fastplays (10-17): the LIVE decision stack decides from the designed Rocket + Tornado scenarios (scenarios.py).

The D3 command gap.py runs (livecal worker = search_s0 with the live rule stack, anti-stall off) + EXTRA, in-process with search_s0's
own _init_worker / Runner.round; only the job is replaced: Runner.setup's match is re-entered at the scenario (scenarios.scenario_reset),
the opponent made passive, the match capped at T0 + HORIZON, every engine tick logged.
    python scenario_model.py OUT "EXTRA" [REPS [CENSUS]]
Seeds 100000 + 1000 * scenario + 100 * time variant + replicate (learner side = replicate parity, as Runner.setup).
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(ROOT / 'scratchpad/gauntlet/L74/gap'), str(ROOT / 'scratchpad/gauntlet/L74/livecal'), str(ROOT)]
import scenarios as SC  # noqa: E402

CK = 'icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt'
E4 = 'icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt'
HORIZON = 300                       # 15 s from T0


def decode(seed):
    s = seed - 100000
    return SC.NAMES[s // 1000], SC.T0S[(s % 1000) // 100], s % 100


def summarise_run(log, plays, spawned, uids, T0, grid):
    from pipeline import engine_play as ep
    out = []
    for q in plays:
        cx, cy = ep.cell_center(q['cell'], grid)
        out.append(dict(tick=q['tick'], land=q.get('land_tick', q['tick']), card=q['card'], cell=q['cell'],
                        xy=(round(cx * 18, 2), round(cy * 32, 2)), why=q['why'], acc=q['accepted'], el=q['elixir_exact']))
    rockets, torn = SC.spell_life(log, 'Rocket'), SC.spell_life(log, 'Tornado')
    imps = []
    for r in rockets:
        imp = SC.impact(log, r, spawned)
        ti = imp.get('impact_tick')
        if ti:
            imp['group_hp_drop'] = SC.group_hp(log, ti - 1, uids) - SC.group_hp(log, ti + 1, uids)
            prior = [t for t in torn if t[0] <= ti]
            imp['impact_minus_tornado_deploy'] = (ti - prior[-1][0]) if prior else None
            imp['deploy'] = r[0]
        imps.append(imp)
    end = log[-1]['t']
    return dict(plays=out, rockets=imps, tornados=[t[:2] for t in torn], group_hp0=SC.group_hp(log, T0, uids),
                group_hp_end=SC.group_hp(log, end, uids),
                group_alive_end=sum(1 for e in log[-1]['enemy'] if e[0] in uids and e[4] > 0),
                etowers0=log[0]['etowers'], etowers_end=log[-1]['etowers'], end_tick=end)


def make_job():
    from pipeline import search_s0 as S

    def job(j):
        arm, opp_id, seed, _ = j
        name, T0, rep = decode(seed)
        run = S._W['runner']
        m = run.setup('gen', seed, list(SC.OPP_DECK))
        env, L = m.env, m.learner.side
        decks = {L: m.spec['learner_deck'], 1 - L: m.spec['opp_deck']}
        spawned = SC.scenario_reset(env, decks, L, name, T0)
        log = SC.track(env, L)
        uids = {e[0] for e in log[0]['enemy']}
        m.learner.next_tick, m.opp.next_tick = env.tick, 10 ** 9      # the opponent never decides
        env.tail_cap = T0 + HORIZON
        st, rng = {k: 0 for k in ('eligible', 'searched', 'unsearched', 'gate_skipped', 'overrides', 'chose_wait',
                                  'plain_wait_overridden', 'moved_cell', 'n_cands')}, random.Random(seed)
        st['search_s'] = 0.0
        while True:
            ds = m.due()
            if not ds:
                break
            run.round(m, ds, 'plain', st, rng)
        res = summarise_run(log, m.learner.plays, spawned, uids, T0, m.learner.cfg['grid'])
        return dict(arm=arm, opp=opp_id, seed=seed, skipped='scenario', scenario=name, T0=T0, rep=rep, learner_side=L,
                    pipeline=dict(getattr(m.learner, 'pipe_n', {}) or {}), follow=dict(getattr(m.learner, 'follow_n', None) or {}),
                    **res)
    return job


def main():
    import gap
    from pipeline import search_s0 as S
    out, extra = Path(sys.argv[1]), sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    seeds = [100000 + 1000 * s + 100 * v + r for s in range(len(SC.NAMES)) for v in range(len(SC.T0S)) for r in range(reps)]
    census = Path(sys.argv[4] if len(sys.argv) > 4 else '/workspace/results/fastplays/smoke/inputs/cal_evo.json')  # unused by
    # the scenario (fixed opponent deck); _init_worker loads it
    job = dict(seeds=seeds, checkpoint=CK, opponent=dict(path=E4, temperature=0.1), fast=False)
    cmd = gap.command('D3', job, census, out, sys.executable, extra.split())
    args = cmd[3:]                                       # after [python, livecal.py, --worker]
    original = S.live_cfg

    def no_stall(*a, **k):                              # livecal.worker: the eval runs without the anti-stall rule
        cfg = original(*a, **k)
        cfg['stall_elixir'] = None
        return cfg
    S.live_cfg = no_stall
    S._run_job = make_job()
    return S.main(args)


if __name__ == '__main__':
    raise SystemExit(main())
