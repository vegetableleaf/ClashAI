"""W14 pod-local telemetry patch (on top of pod/o3_patch.py) for the ISOLATED eval copy's pipeline/search_s0.py (its hard link
is already broken by opp_eval_fin15.sh; cb_stepd is never touched). Absent env O3_POS = the code path is skipped (identical
rows; checked by replaying R6 u20 on block 741200, 480 / 480 rows identical). With O3_POS=1 each eval row gets:
  o3_pos   = [[env tick, team, card, x, y]] of every ACCEPTED card deploy (env.eng.act: pool units, 1000 per tile, the
             engine's global frame; ability presses excluded);
  o3_trace = {"towers": {uid: [team, slot, max_hp]}, "snaps": [[tick, [[uid, hp] per crown tower], [[uid, team, hp,
             target_uid] per X-Bow]]]}: the REAL match's state after each env.core.step call (search forks run on other
             envs, fork_into copies neither core nor eng), kept only when a tower hp or an X-Bow / its target changed.
The wrappers only read. Idempotent (v2 marker); refuses if the anchor moved.   python pos_patch.py PATH/search_s0.py"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
t = p.read_text(encoding='utf-8')
ANCHOR = '    rec = _W["runner"].play(arm, m, deadline or None)\n'
HELPER = '''

class _W14CoreRec:   # W14 pod-local telemetry (opp_model/w14/pos_patch.py v2): records the real match after each step
    def __init__(self, core, env, out):
        self._c, self._e, self._o, self._last = core, env, out, None

    def __getattr__(self, k):
        return getattr(self._c, k)

    def step(self, *a, **kw):
        r = self._c.step(*a, **kw)
        try:
            st = self._c.state()
            names = self._e.names
            tw, xb = [], []
            for e in st.entities:
                if e.tower_slot >= 0:
                    self._o["towers"].setdefault(int(e.uid), [int(e.team), int(e.tower_slot), int(e.max_hp)])
                    tw.append([int(e.uid), int(e.hp)])
                else:
                    try:
                        nm = str(names[e.card_id])
                    except (KeyError, IndexError, TypeError):
                        nm = ""
                    if nm.replace("-", "").replace("_", "").lower() == "xbow":
                        xb.append([int(e.uid), int(e.team), int(e.hp), int(e.target_uid)])
            key = (tw, xb)
            if key != self._last:
                self._o["snaps"].append([int(st.tick), tw, xb])
                self._last = key
        except Exception as ex:  # noqa: BLE001 -- telemetry must never break a match
            self._o["err"] = repr(ex)
        return r
'''
NEW = ('    _o3pos = None\n'
       "    if __import__('os').environ.get('O3_POS'):   # W14 pod-local telemetry (opp_model/w14/pos_patch.py v2)\n"
       '        _env, _o3pos, _o3tr = m.env, [], {"towers": {}, "snaps": []}\n'
       '        _act, _core0 = _env.eng.act, _env.core\n'
       '        def _rec_act(*, side, deck_index=-1, x=0, y=0, ability_button=None, _a=_act, _e=_env, _l=_o3pos):\n'
       '            r = _a(side=side, deck_index=deck_index, x=x, y=y, ability_button=ability_button)\n'
       '            if ability_button is None and r.get("accepted"):\n'
       '                _l.append([int(_e.tick), int(side), str(_e.names[_e.deck_ids[side][deck_index]]), int(x), int(y)])\n'
       '            return r\n'
       '        _env.eng.act = _rec_act\n'
       '        _env.core = _W14CoreRec(_core0, _env, _o3tr)\n'
       '    try:\n'
       '        rec = _W["runner"].play(arm, m, deadline or None)\n'
       '    finally:\n'
       '        if _o3pos is not None:\n'
       '            del _env.eng.act                     # back to the class method\n'
       '            _env.core = _core0\n'
       '    if _o3pos is not None:\n'
       '        rec["o3_pos"], rec["o3_trace"] = _o3pos, _o3tr\n')
if '_W14CoreRec' in t:
    print('already patched (v2)')
    sys.exit(0)
if '_o3pos' in t:
    sys.exit('v1 patch present: restore the pre-patch copy first')
if t.count(ANCHOR) != 1:
    sys.exit(f'anchor found {t.count(ANCHOR)} times: refusing')
t = t.replace(ANCHOR, NEW) + HELPER
tmp = p.with_suffix('.py.w14tmp')
tmp.write_text(t, encoding='utf-8')
tmp.replace(p)                                  # atomic: a running import never sees a half-written file
print('patched v2', p)
