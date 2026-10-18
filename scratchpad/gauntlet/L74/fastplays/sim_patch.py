"""L74 fastplays (10-17): two SIM-side patches for the fast-plays eval, applied to a POD checkout only (never main, never live).
    python sim_patch.py CHECKOUT        (idempotent: an already-patched file is left alone; any other mismatch aborts)

P1 (measurement only) search_s0 --record-plays rows also carry each play's decided cell and `why` (combo geometry, rule vs model).
P2 (SIM twin of live) e1_eval SelfPlaySide: a decision that carries follow_ups (the --rocket-tornado combo) may run with
   cfg['pipeline_decisions'] too, as live_play does with --follow-up-taps + --pipeline-decisions: today's SIM raises
   "follow_ups and pipeline_decisions are separate mechanisms". Live rule (live_play.py ~1306): no pipelined decision while a
   follow-up is scheduled; once it is resolved, decisions resume on the reader-frame grid when fewer than FOLLOW_MAX_OUT taps are
   out (SIM: _pipe_next_tick). Without pipeline_decisions every line runs exactly as before (the patch is inside `if self.pipe`).
"""
import sys
from pathlib import Path

PATCHES = [
    ("pipeline/search_s0.py",
     '        rec["own_plays"] = [[q["tick"], q.get("land_tick", q["tick"]), q["card"], q["accepted"], q["elixir_exact"]]\n',
     '        rec["own_plays"] = [[q["tick"], q.get("land_tick", q["tick"]), q["card"], q["accepted"], q["elixir_exact"],\n'
     '                             q["cell"], q["why"]]   # FASTPLAYS P1 (pod-only): + decided cell, why\n'),
    ("pipeline/e1_eval.py",
     '            if self.pipe:\n'
     '                raise ValueError("follow_ups and pipeline_decisions are separate mechanisms: use one")\n'
     '            if not delay:\n'
     '                raise ValueError("follow_ups need cfg[\'action_delay_ticks\'] > 0 in a SelfPlaySide")\n'
     '            self._follow_start(p, d, tick)\n'
     '            return\n',
     '            if not delay:\n'
     '                raise ValueError("follow_ups need cfg[\'action_delay_ticks\'] > 0 in a SelfPlaySide")\n'
     '            self._follow_start(p, d, tick)\n'
     '            if self.pipe:   # FASTPLAYS P2 (pod-only): live --follow-up-taps + --pipeline-decisions (live_play ~1306)\n'
     '                self._pipe_ready = tick + int(self.cfg.get("follow_arrival_ticks", FOLLOW_ARRIVAL_TICKS))\n'
     '                self._hz_step_ticks = 0\n'
     '            return\n'),
    ("pipeline/e1_eval.py",
     '            self.next_tick = f["tick"] + self.cfg["decide_every"] * ((f["last"] - f["tick"]) // self.cfg["decide_every"] + 1)\n',
     '            self.next_tick = f["tick"] + self.cfg["decide_every"] * ((f["last"] - f["tick"]) // self.cfg["decide_every"] + 1)\n'
     '            if self.pipe:   # FASTPLAYS P2: nothing scheduled -> the reader-frame grid, < FOLLOW_MAX_OUT taps out\n'
     '                self.next_tick = self._pipe_next_tick(int(self.env.tick))\n'),
]


def main(root):
    root = Path(root)
    for rel, old, new in PATCHES:
        p = root / rel
        s = p.read_text(encoding="utf-8")
        if new in s:
            print("already", rel)
            continue
        if s.count(old) != 1:
            raise SystemExit(f"{rel}: patch anchor found {s.count(old)} times")
        p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
        print("patched", rel)


if __name__ == "__main__":
    main(sys.argv[1])
