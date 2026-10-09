"""Follow-up plays (the Rocket + Tornado combo's second tap) for the SELF-PLAY side the SIM v3 benchmark runs on.
pipeline/e1_eval.py schedules follow_ups only in the ghost Match (SelfPlaySide.apply raises NotImplementedError), and the benchmark's
`--opps gen` opponent is a SelfPlaySide.  This module patches the two classes IN THE PROCESS (import it before running the match; a repo
change would belong in e1_eval.py, which is outside this ticket's write set).  Semantics = Match._apply_follow_ups' timing:
  * the decided play A lands at T + delay (delay 0 in the benchmark); each follow-up lands at A's landing + max(after_ticks - arrival, 0)
    (arrival = cfg follow_arrival_ticks, default e1_eval.FOLLOW_ARRIVAL_TICKS) -- the SIM engine accepts it if it is affordable and in
    the hand AT THAT TICK and refuses it otherwise (counted like any refusal, tally 'refused'); the live rule would WAIT inside its window
    for the elixir, so the SIM is the stricter of the two;
  * a follow-up whose first play was refused is dropped (require_first, tally 'cancelled_first_unconfirmed');
  * this side takes no decision until the last of them has landed (next grid tick after), as for a single delayed play.
The ghost Match's tally key is the match row's `follow_ups` ({'fired': n, 'refused': n, 'cancelled_...': n})."""
import json, os
from collections import Counter

import pipeline.e1_eval as E

_out = None


def _log(self, d, land, result):
    """<FIRE_DIR>/fu_<pid>.jsonl: one line per follow-up outcome (the match row has no tally on the self-play side)."""
    global _out
    if os.environ.get('FIRE_DIR'):
        if _out is None:
            _out = open(os.path.join(os.environ['FIRE_DIR'], f'fu_{os.getpid()}.jsonl'), 'a', buffering=1)
        _out.write(json.dumps(dict(tag=str(self.entry.get('tag')), land=int(land), slot=int(d['slot']), result=result)) + chr(10))


_orig_apply, _orig_land, _orig_due = E.SelfPlaySide.apply, E.SelfPlaySide._land, E.SelfPlayMatch.due


def apply(self, p, d):
    if not (d['play'] and d.get('follow_ups')):
        return _orig_apply(self, p, d)
    tick = self._record(p, d)
    if getattr(self.env, 'hero_abilities', False):
        for side, commands in self._ability_commands.items():
            self.env.queue_abilities(side, commands, self.delay)
    de, delay = self.cfg['decide_every'], self.delay
    arrival = int(self.cfg.get('follow_arrival_ticks', E.FOLLOW_ARRIVAL_TICKS))
    land_a = tick + delay
    queue = [(land_a, p, d)]
    for fu in d['follow_ups']:
        queue.append((land_a + max(int(fu['after_ticks']) - arrival, 0), p,
                      {'play': True, 'slot': fu['slot'], 'cell': fu['cell'], 'why': 'follow_up', 'require_first': bool(fu.get('require_first', True))}))
    queue.sort(key=lambda q: q[0])
    self.pending, self.more = queue[0], queue[1:]
    self._first_failed = False
    if getattr(self, 'follow_n', None) is None:
        self.follow_n = Counter()
    last = queue[-1][0]
    self.next_tick = tick + de * ((last - tick) // de + 1)


def _land(self, p, d, land, landed):
    if d.get('why') == 'follow_up':
        if d.get('require_first') and getattr(self, '_first_failed', False):
            self.follow_n['cancelled_first_unconfirmed'] += 1
            _log(self, d, land, 'cancelled_first_unconfirmed')
            return False
        acc = _orig_land(self, p, d, land, landed)
        self.follow_n['fired' if acc else 'refused'] += 1
        _log(self, d, land, 'fired' if acc else 'refused')
        return acc
    acc = _orig_land(self, p, d, land, landed)
    if not acc:
        self._first_failed = True                    # read only by this play's follow-ups; apply() resets it
    return acc


def due(self):
    env = self.env
    while True:
        t = int(env.tick)
        for s in self.sides:
            while s.pending and s.pending[0] <= t and not env.terminated:
                (land, p, d), s.pending = s.pending, (s.more.pop(0) if getattr(s, 'more', None) else None)
                s._land(p, d, land, True)
        if env.done:
            for s in self.sides:
                while s.pending:
                    (land, p, d), s.pending = s.pending, (s.more.pop(0) if getattr(s, 'more', None) else None)
                    s._land(p, d, land, False)
            return []
        ds = [s for s in self.sides if s.next_tick <= t]
        if ds:
            raw = env.raw()
            for s in ds:
                s.state = raw
            return ds
        nxt = min([s.next_tick for s in self.sides] + [s.pending[0] for s in self.sides if s.pending])
        env._advance_to(min(nxt, env.tail_cap))


E.SelfPlaySide.apply, E.SelfPlaySide._land, E.SelfPlayMatch.due = apply, _land, due
