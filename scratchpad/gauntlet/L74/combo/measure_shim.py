"""L74 combo eval (10-17), MEASUREMENT ONLY, pod checkout cb_combo: livecal.worker calls install(S) when COMBO_MEASURE=1
(pod_patch.py adds that one line there). Decisions are untouched -- it only reads:
  rec["own_plays_x"]  = every learner play [decision tick, landing tick, card, accepted, elixir seen, cell, why] (= fastplays P1)
  rec["combo_rule"]   = every rocket_tornado decision of the rule: tick, the value its model expected the pull + blast to hold
                        (rocket_tornado_choice re-run on the same inputs: a pure function), order, cell, plan
(the Rocket impacts themselves come from search_s0 --spell-log: pipeline.spell_value.SpellTracker)."""


def install(S):
    from pipeline import decision_options as D
    orig = D.decide_batch

    def decide_batch(model, enc, heads, p, allowed, stalled, **kw):
        out = orig(model, enc, heads, p, allowed, stalled, **kw)
        rv, opts = kw.get('rocket_value'), kw.get('options')
        for r, d in enumerate(out):
            if rv and d.get('why') == 'rocket_tornado':
                bs, pending, holder = rv[r]
                hit = D.rocket_tornado_choice(opts, kw['card_names'][r], allowed[r], bs, kw['grid'], pending)
                holder.__dict__.setdefault('_combo_rule', []).append(dict(
                    tick=int(round(float(bs.t_sec) / 0.05)), cell=int(d['cell']), value=None if hit is None else round(float(hit[4]), 3),
                    order=None if hit is None else (hit[5] if len(hit) > 5 else 'rocket'), plan=None if hit is None else list(hit[3])))
        return out
    D.decide_batch = decide_batch

    last = {}
    orig_setup = S.setup_job

    def setup_job(*a, **kw):
        got = orig_setup(*a, **kw)
        last['m'] = None if got is None else got[0]
        return got
    S.setup_job = setup_job
    orig_job = S._run_job

    def _run_job(job):
        last['m'] = None
        rec = orig_job(job)
        m = last.get('m')
        if m is not None and not rec.get('skipped'):
            rec['own_plays_x'] = [[q['tick'], q.get('land_tick', q['tick']), q['card'], q['accepted'], q['elixir_exact'], q['cell'], q['why']]
                                  for q in S._W['runner'].last_result['plays']]
            rec['combo_rule'] = list(getattr(m.learner, '_combo_rule', ()))
        return rec
    S._run_job = _run_job
