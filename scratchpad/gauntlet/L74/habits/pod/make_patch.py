"""Build the SIM-ONLY habits probe copy of the pod's pipeline/search_s0.py (sha 1538024e, the code CLIII's 642/960 was
scored with). Never deployed live: the copy lives only in the pod checkout /workspace/habits/cb. All opt-in via env vars
(gap.py passes os.environ to its workers); unset = the original behaviour byte for byte in decisions.
  HABITS_REC=1             each match row gets "hab": both sides' plays (+ engine x, y) and a 20-tick board sample
  HABITS_XBOW_GATE=N       refuse our OFFENSIVE X-Bow (cell y/32 < 0.64) when the counter the model sees is >= N
  HABITS_GATE_MODE=wait|mask   wait = no play this decision (default); mask = re-decide with the X-Bow slot disallowed
  HABITS_OPP_CONST=v       the learner model's opp_elixir input replaced by the constant v (ablation)
    python make_patch.py  -> search_s0.py next to this file
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / 'orig' / 'search_s0.py').read_text(encoding='utf-8')


def sub(old, new):
    global src
    assert src.count(old) == 1, (src.count(old), old[:80])
    src = src.replace(old, new)


sub("import zlib\n", "import os\nimport zlib\n")
sub("class Runner:\n", '''HAB_REC = os.environ.get("HABITS_REC") == "1"
HAB_GATE = float(os.environ["HABITS_XBOW_GATE"]) if os.environ.get("HABITS_XBOW_GATE") else None
HAB_GATE_MODE = os.environ.get("HABITS_GATE_MODE", "wait")
HAB_OPP = float(os.environ["HABITS_OPP_CONST"]) if os.environ.get("HABITS_OPP_CONST") else None
HAB_EVERY = 20


def hab_sample(m, s) -> list:
    """[tick, opp truth, counter now (true counter), model's opp input, own elixir, towers [side, type, x, y, hp],
    enemy bodies on/near our half [uid, name, hp, max_hp, x, y], own X-Bows [uid, hp, x, y]] (engine tiles)."""
    tick, bs, view = s._cur
    raw = s.state
    pub = s.public
    est = getattr(pub, "_hab_est", pub.estimate_at)(tick) if pub is not None else None
    tw = [[t["side"], t["type"][0], round(t["x"], 1), round(t["y"], 1), int(t["hp"])]
          for t in raw["episode"]["crown_towers"]]
    en = [[e["entity_id"], e["name"], int(e["hp"]), int(e["max_hp"]), round(e["x"], 1), round(e["y"], 1)]
          for e in raw["entities"] if e["side"] != s.side]
    xb = [[e["entity_id"], int(e["hp"]), round(e["x"], 1), round(e["y"], 1)]
          for e in raw["entities"] if e["side"] == s.side and str(e["name"]).lower().replace("-", "") == "xbow"]
    return [int(tick), None if bs.opp_elixir is None else round(float(bs.opp_elixir), 3),
            None if est is None else round(float(est), 3), None if view.opp_elixir is None else round(float(view.opp_elixir), 3),
            round(float(bs.my_elixir), 3), tw, en, xb]


def hab_plays(side) -> list:
    out = []
    for q in side.plays:
        X, Y = side.ep.cell_to_engine(q["cell"], side.mirror, side.cfg["grid"])
        x, y = side.ep.cell_center(q["cell"], side.cfg["grid"])
        out.append([int(q["tick"]), int(q.get("land_tick", q["tick"])), q["card"], bool(q["accepted"]), q["why"],
                    q["elixir_exact"], round(float(x), 2), round(float(y), 2), X, Y])
    return out


class Runner:
''')
sub('''        if getattr(self, "habit_log", False):
            m.habit_dec = {}''', '''        if HAB_GATE is not None:
            st.update(hab_gate_seen=0, hab_gate_refused=0, hab_gate_masked_play=0)
        if HAB_REC:
            m.hab_samples = []
        if getattr(self, "habit_log", False):
            m.habit_dec = {}''')
sub('''        for s in ds:
            s.prepare()
        todo = []''', '''        if HAB_OPP is not None and m.learner in ds and m.learner.public is None:
            from pipeline.public_observation import PublicObserver
            L = m.learner                                   # created as e1_eval prepare() would, then the input replaced
            L.public = PublicObserver(L.side, schedule=getattr(L.env, 'elixir_regen_schedule', None))
            L.public._hab_est = L.public.estimate_at
            L.public.estimate_at = lambda tick, _v=HAB_OPP: _v
        for s in ds:
            s.prepare()
            if HAB_REC and s is m.learner and (not m.hab_samples or s._cur[0] - m.hab_samples[-1][0] >= HAB_EVERY):
                m.hab_samples.append(hab_sample(m, s))
        todo = []''')
sub('''            if s is m.learner and self.probe_xbow_focus and d["play"]:''', '''            if s is m.learner and HAB_GATE is not None and d["play"]:
                d = self.hab_gate(s, d, st, enc, heads, p, allowed, stalled)
            if s is m.learner and self.probe_xbow_focus and d["play"]:''')
sub('''    def probe_xbow(self, s, enc, d: dict, st: dict) -> dict:''', '''    def hab_gate(self, s, d, st, enc, heads, p, allowed, stalled) -> dict:
        """SIM-only habits probe: an OFFENSIVE X-Bow (habits' XBOW_BRIDGE_Y cut) while the counter the model sees is >=
        HAB_GATE is refused: wait, or re-decided with the X-Bow slot disallowed (mask)."""
        from pipeline.decision_options import cell_centres_tiles, is_xbow
        from pipeline.e1_eval import live_decide_batch
        if not is_xbow(s.deck.cards[d["slot"]]):
            return d
        ys = cell_centres_tiles(s.cfg["grid"])[1]
        if float(ys[int(d["cell"])]) / 32.0 >= XBOW_BRIDGE_Y:
            return d
        st["hab_gate_seen"] += 1
        est = s._cur[2].opp_elixir
        if est is None or est < HAB_GATE:
            return d
        st["hab_gate_refused"] += 1
        if HAB_GATE_MODE == "mask":
            a2 = allowed.copy()
            a2[d["slot"]] = False
            if a2.any():
                tau, kw = E.posture_live([s], enc, s.cfg, s.cfg["tau"], decision_match_kwargs([s]))
                d2 = live_decide_batch(s.model, enc, heads, [p], a2[None], np.array([stalled]), tau=tau,
                                       device=s.cfg["device"], **kw)[0]
                st["hab_gate_masked_play"] += int(bool(d2["play"]))
                return {**d2, "why": "hab_gate_mask:" + str(d2.get("why"))}
        return {"play": False, "slot": -1, "cell": -1, "why": "hab_xbow_gate"}

    def probe_xbow(self, s, enc, d: dict, st: dict) -> dict:''')
sub('''    if getattr(_W["runner"], "habit_log", False):           # --habit-log: the learner's habit counts (measurement only)
        rec["habits"] = habits(m)''', '''    if getattr(_W["runner"], "habit_log", False):           # --habit-log: the learner's habit counts (measurement only)
        rec["habits"] = habits(m)
    if HAB_REC:                                             # SIM-only habits probe record (L74/habits)
        L, O = m.learner, m.opp
        rec["hab"] = {"own": hab_plays(L), "opp": hab_plays(O), "samples": m.hab_samples,
                      "L": int(L.side), "mirror": [bool(L.mirror), bool(O.mirror)],
                      "env": {k: os.environ.get(k) for k in ("HABITS_XBOW_GATE", "HABITS_GATE_MODE", "HABITS_OPP_CONST")}}''')
(HERE / 'search_s0.py').write_bytes(src.encode('utf-8'))
print('ok', len(src))
