p='hogeq/src/clashrl/train_sim_ppo.py'
s=open(p,encoding='utf-8').read()
def rep(old,new):
    global s
    assert s.count(old)==1,(old[:70],s.count(old)); s=s.replace(old,new)
rep('''    gate_prior_coef = float(cfg.get("sim", "ppo_gate_prior_coef", default=0.0))
    _gprior = None
    if gate_prior_coef > 0.0:
        import json as _gjson
        _gpp = cfg.path(cfg.get("sim", "ppo_gate_prior_path", default="config/gate_prior.json"))
        _gj = _gjson.loads(Path(_gpp).read_text(encoding="utf-8"))
        assert _gj.get("schema") == 1, "gate prior: unknown schema"
        _greg, _got = float(_gj["regulation_s"]), float(_gj["overtime_s"])
        _gprior = (np.asarray([_gj["p_play"][p] for p in ("single", "double", "triple")], np.float32),
                   _greg - 60.0, _greg + max(0.0, _got - 60.0))
        print("[train-sim-ppo] GATE PRIOR ON: coef %.3f, %s (%d replays, dt %.1f s; single-elixir "
              "P(play) at 4 / 7 / 9 elixir = %.2f / %.2f / %.2f)"
              % (gate_prior_coef, _gpp, int(_gj.get("replays", 0)), float(_gj.get("dt", 0.0)),
                 _gprior[0][0][4], _gprior[0][0][7], _gprior[0][0][9]))
    _gpstat = {"n": 0, "ce": 0.0, "pi": 0.0, "p": 0.0, "rows": 0, "seen": 0}
''','''    gate_prior_coef = float(cfg.get("sim", "ppo_gate_prior_coef", default=0.0))
    # THE THIRD KEY (HANDOFF 5bw/5bx): the ruling's "threat on our half" was dropped from v0, and
    # the blended table pulls "wait" twice as hard as pros on rows where the opponent just played a
    # troop (5-7 elixir: pros play 8.6/6.8/6.6% under pressure vs 2.4/3.0/2.9% quiet). W > 0 reads
    # a schema-2 table split by "opponent troop within W s" and keys the sim rows on "youngest
    # living enemy troop younger than W s" (SimMatchEnv.enemy_troop_min_age). 0.0 = the blended
    # table, byte-for-byte what the gate05 run trained on.
    gate_prior_pressure_s = float(cfg.get("sim", "ppo_gate_prior_pressure_s", default=0.0))
    _gprior = None
    if gate_prior_coef > 0.0:
        import json as _gjson
        _gpp = cfg.path(cfg.get("sim", "ppo_gate_prior_path", default="config/gate_prior.json"))
        _gj = _gjson.loads(Path(_gpp).read_text(encoding="utf-8"))
        assert _gj.get("schema") in (1, 2), "gate prior: unknown schema"
        _greg, _got = float(_gj["regulation_s"]), float(_gj["overtime_s"])
        if gate_prior_pressure_s > 0.0:
            assert _gj.get("schema") == 2, "gate prior: ppo_gate_prior_pressure_s > 0 needs a schema-2 table"
            assert abs(float(_gj["pressure_s"]) - gate_prior_pressure_s) < 1e-6, (
                "gate prior: table fit at W=%s s, config asks %s s" % (_gj["pressure_s"], gate_prior_pressure_s))
            _gtab0 = np.asarray([[_gj["p_play_by_pressure"][p][k] for k in ("quiet", "pressure")]
                                 for p in ("single", "double", "triple")], np.float32)   # [phase, pres, bucket]
        else:
            _gtab0 = np.asarray([_gj["p_play"][p] for p in ("single", "double", "triple")], np.float32)
        _gprior = (_gtab0, _greg - 60.0, _greg + max(0.0, _got - 60.0))
        if gate_prior_pressure_s > 0.0:
            print("[train-sim-ppo] GATE PRIOR ON: coef %.3f, %s (%d replays, dt %.1f s; PRESSURE key W=%.0f s; "
                  "single-elixir P(play) at 4 / 7 / 9 elixir quiet %.3f / %.3f / %.3f, pressure %.3f / %.3f / %.3f)"
                  % (gate_prior_coef, _gpp, int(_gj.get("replays", 0)), float(_gj.get("dt", 0.0)),
                     gate_prior_pressure_s, _gtab0[0][0][4], _gtab0[0][0][7], _gtab0[0][0][9],
                     _gtab0[0][1][4], _gtab0[0][1][7], _gtab0[0][1][9]))
        else:
            print("[train-sim-ppo] GATE PRIOR ON: coef %.3f, %s (%d replays, dt %.1f s; single-elixir "
                  "P(play) at 4 / 7 / 9 elixir = %.2f / %.2f / %.2f)"
                  % (gate_prior_coef, _gpp, int(_gj.get("replays", 0)), float(_gj.get("dt", 0.0)),
                     _gprior[0][0][4], _gprior[0][0][7], _gprior[0][0][9]))
    _gpstat = {"n": 0, "ce": 0.0, "pi": 0.0, "p": 0.0, "rows": 0, "seen": 0, "pres": 0.0}
''')
rep('''        gp_f = gpm_f = None
        if _gprior is not None and roll.get("t"):
            _gtab, _gdbl, _gtri = _gprior
            _gt = np.asarray(flat("t"), np.float32)
            _gph = np.where(_gt >= _gtri, 2, np.where(_gt >= _gdbl, 1, 0))
            _geb = np.clip(np.floor(np.asarray([float(e[0]) for e in elx_f]) * 10.0 + 1e-6),
                           0, 10).astype(np.int64)
            gp_f = torch.tensor(_gtab[_gph, _geb], dtype=torch.float32, device=device)
''','''        gp_f = gpm_f = gpr_f = None
        if _gprior is not None and roll.get("t"):
            _gtab, _gdbl, _gtri = _gprior
            _gt = np.asarray(flat("t"), np.float32)
            _gph = np.where(_gt >= _gtri, 2, np.where(_gt >= _gdbl, 1, 0))
            _geb = np.clip(np.floor(np.asarray([float(e[0]) for e in elx_f]) * 10.0 + 1e-6),
                           0, 10).astype(np.int64)
            if _gtab.ndim == 3:
                # PRESSURE key: youngest living enemy troop younger than W s (same event as the
                # table's "opponent troop played within W s")
                _gpr = (np.asarray(flat("eage"), np.float32) < gate_prior_pressure_s).astype(np.int64)
                gp_f = torch.tensor(_gtab[_gph, _gpr, _geb], dtype=torch.float32, device=device)
                gpr_f = torch.tensor(_gpr, dtype=torch.float32, device=device)
            else:
                gp_f = torch.tensor(_gtab[_gph, _geb], dtype=torch.float32, device=device)
''')
rep('''                        _gpstat["pi"] += float(lp_g[_gpk, 1].exp().mean())
                        if _gpstat["n"] == 1 or _gpstat["n"] % 200 == 0:
                            print("[train-sim-ppo]   GATE PRIOR CE %.4f over %d updates | pi(play) %.3f "
                                  "vs prior %.3f on the same rows | %.0f%% of rows usable"
                                  % (_gpstat["ce"] / _gpstat["n"], _gpstat["n"],
                                     _gpstat["pi"] / _gpstat["n"], _gpstat["p"] / _gpstat["n"],
                                     100.0 * _gpstat["rows"] / max(1, _gpstat["seen"])), flush=True)
''','''                        _gpstat["pi"] += float(lp_g[_gpk, 1].exp().mean())
                        if gpr_f is not None:
                            _gpstat["pres"] += float(gpr_f[mb_t][_gpk].mean())
                        if _gpstat["n"] == 1 or _gpstat["n"] % 200 == 0:
                            print("[train-sim-ppo]   GATE PRIOR CE %.4f over %d updates | pi(play) %.3f "
                                  "vs prior %.3f on the same rows | %.0f%% of rows usable%s"
                                  % (_gpstat["ce"] / _gpstat["n"], _gpstat["n"],
                                     _gpstat["pi"] / _gpstat["n"], _gpstat["p"] / _gpstat["n"],
                                     100.0 * _gpstat["rows"] / max(1, _gpstat["seen"]),
                                     (" | PRESSURE on %.0f%% of them" % (100.0 * _gpstat["pres"] / _gpstat["n"]))
                                     if gpr_f is not None else ""), flush=True)
''')
rep('''        ct = [float(p.get("t", 0.0)) for p in rpool.last]      # engine clock, for the gate prior's phase
''','''        ct = [float(p.get("t", 0.0)) for p in rpool.last]      # engine clock, for the gate prior's phase
        ceage = [float(p.get("eage", 1e9)) for p in rpool.last]  # youngest enemy troop, its PRESSURE key
''')
rep('''        ct = [float(getattr(getattr(e, "eng", None), "t", 0.0)) for e in pool]
''','''        ct = [float(getattr(getattr(e, "eng", None), "t", 0.0)) for e in pool]
        ceage = [float(e.enemy_troop_min_age()) if hasattr(e, "enemy_troop_min_age") else 1e9 for e in pool]
''')
rep('''"sil": [], "isdrill": [], "boot": None, "t": [],''','''"sil": [], "isdrill": [], "boot": None, "t": [], "eage": [],''')
rep('''                roll["thr"].append([t.copy() for t in cthr]); roll["t"].append(list(ct))
''','''                roll["thr"].append([t.copy() for t in cthr]); roll["t"].append(list(ct))
                roll["eage"].append(list(ceage))
''')
rep('''                        ct[i] = float(pay.get("t", 0.0))
''','''                        ct[i] = float(pay.get("t", 0.0))
                        ceage[i] = float(pay.get("eage", 1e9))
''')
rep('''                        ct[i] = float(getattr(getattr(env, "eng", None), "t", 0.0))
''','''                        ct[i] = float(getattr(getattr(env, "eng", None), "t", 0.0))
                        ceage[i] = float(env.enemy_troop_min_age()) if hasattr(env, "enemy_troop_min_age") else 1e9
''')
open(p,'w',encoding='utf-8').write(s); print("trainer patched")
