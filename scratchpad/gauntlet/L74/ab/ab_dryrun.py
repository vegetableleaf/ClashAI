"""Deterministic fake supervisor + incremental public log writer. No processes/network."""
from datetime import datetime
import json
import os
from pathlib import Path

from live_ab import Arm, sha256


def towers(hp=4424, own=3, enemy=3, side=1):
    bodies = []
    for team, alive in ((side, own), (1-side, enemy)):
        for i, x in enumerate((9000, 3500, 14500)):
            bodies.append(dict(card_id=-1, side=team, x=x,
                               y=(3000 if team == 0 else 29000) if i == 0 else (6500 if team == 0 else 25500),
                               hp=(7032 if i == 0 else hp) if i < alive else 0,
                               max_hp=7032 if i == 0 else hp))
    return bodies


def decision(tick=20, hp=4424, xbow=True, own=3, enemy=3, side=1):
    return dict(event='decision', tick=tick, public=dict(
        observer_side=side, raw_bodies=towers(hp, own, enemy, side),
        own_hand=[dict(name='Xbow' if xbow else 'GoblinBarrel', deck_index=4)]))


def emit(path, *events):
    with path.open('a', encoding='utf8') as f:
        for e in events:
            f.write(json.dumps(e)+'\n')


class FakeSupervisor:
    def __init__(self, root, scenario='normal', *, noise=False, absent=False, extra=None):
        self.root = Path(root)
        self.live, self.logs, self.output = [self.root / n for n in ('live', 'logs', 'ab')]
        for p in (self.live, self.logs, self.output):
            p.mkdir(parents=True)
        self.originals = {'CKPT_OVERRIDE': b'C:/original checkpoint.pt\r\n', 'LIVE_FAST': b'off\r\n'}
        if absent:
            self.originals = dict.fromkeys(self.originals)
        for name, data in self.originals.items():
            if data is not None:
                (self.live / name).write_bytes(data)
        for name, data in {'LIVE_OPTIONS': b'{"untouched":true}\r\n', 'LIVE_DECK': b'icebow\n',
                           'LIVE_EMOTES': b'on\n', 'HAND_READER_ENABLED': b'0\n'}.items():
            (self.live / name).write_bytes(data)
        self.protected = {p.name: p.read_bytes() for p in self.live.iterdir() if p.name not in self.originals}
        self.arms = []
        for key in ('A', 'B'):
            path = self.root / (key + ' model.pt')
            path.write_bytes(key.encode())
            self.arms.append(Arm(key, 'fake '+key, path, key == 'B', sha256(path), (extra or {}).get(key, '')))
        self.scenario, self.noise = scenario, noise
        self.t = datetime(2030, 1, 1).timestamp()
        self.alive = False
        self.current = None
        self.arm = None
        self.starts, self.checks, self.posts, self.sequence, self.options_seen = [], [], [], [], []
        self.from_file = {}
        self.serial = self.completed = 0
        self.noise_done = False
        self.stop_seen_while_active = 0
        self.stop_ticks = 0

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(seconds, 1)
        self.step()

    def running(self):
        return int(self.alive)

    def starting(self):
        return False

    def check(self, arm):
        assert not self.alive, 'check must follow supervisor end'
        assert (self.live / 'CKPT_OVERRIDE').read_text().strip() == arm.ckpt.as_posix()
        assert (self.live / 'LIVE_FAST').read_text().strip() == ('on' if arm.fast else 'off')
        self.checks.append(arm.key)
        self.options_seen.append((arm.key, (self.live / 'LIVE_OPTIONS').read_bytes()))
        return self.scenario != 'check_fail'

    def start(self, arm):
        assert not self.alive, 'overlapping supervisors'
        assert self.checks[-1] == arm.key
        (self.live / 'STOP').unlink(missing_ok=True)
        self.arm = arm
        # live_play logs the LIVE_OPTIONS flags it applied as live_options.from_file (dest -> value).
        self.from_file = {t[2:].replace('-', '_'): True for t in (self.live / 'LIVE_OPTIONS').read_text().split()
                          if t.startswith('--')}
        self.starts.append(arm.key)
        self.alive = self.scenario != 'dead'
        self.current = None
        self.noise_done = False

    def post(self, text):
        self.posts.append(text)
        return self.scenario != 'post_fail'

    def filename(self, tag=''):
        self.serial += 1
        return self.logs / ('live_play_' + datetime.fromtimestamp(self.t).strftime('%Y%m%d_%H%M%S')
                            + f'_{self.serial:04d}{tag}.jsonl')

    def header(self, **overrides):
        h = dict(event='start', ckpt=str(self.arm.ckpt), ckpt_sha256=self.arm.sha, dry_run=False,
                 live_options=dict(from_file=dict(self.from_file)))
        if self.arm.fast:
            h['pipeline_decisions'] = True
        h.update(overrides)
        return h

    def junk(self):
        variants = [dict(ckpt_sha256='0'*64), dict(pipeline_decisions=not self.arm.fast),
                    dict(ckpt_sha256=None), dict(dry_run=True), dict(pipeline_decisions='false'),
                    dict(pipeline_decisions=1)]
        flags = frozenset().union(*(a.dests for a in self.arms))
        if flags:   # the other arm's LIVE_OPTIONS share: must never count for this arm
            variants.append(dict(live_options=dict(from_file={d: True for d in flags - self.arm.dests})))
        for h in variants:
            emit(self.filename('_noise'), self.header(**h), decision(), decision(3000, enemy=2),
                 dict(event='end'))
        emit(self.filename('_short'), self.header(), decision(), dict(event='end'))
        old = self.logs / 'live_play_20000101_000000_late_copy.jsonl'
        emit(old, self.header(), decision(), decision(3000, enemy=2), dict(event='end'))

    def step(self):
        if not self.alive:
            return
        stop = (self.live / 'STOP').exists()
        if self.scenario == 'stall':
            if stop:
                self.alive = False
            return
        if self.scenario == 'slow_stop' and stop and self.current is None:
            self.stop_ticks += 1
            if self.stop_ticks < 6:
                return
        if self.current:
            if stop:
                self.stop_seen_while_active += 1
            if self.scenario == 'partial' and self.current[1] == 0:
                with self.current[0].open('ab') as f:
                    f.write(b'{"event": "end"')
                self.current = (self.current[0], 1)
                return
            if self.scenario == 'partial':
                with self.current[0].open('ab') as f:
                    f.write(b'}\n')
            else:
                outcome = self.completed % 3
                emit(self.current[0], decision(3000, own=2 if outcome == 1 else 3,
                                              enemy=2 if outcome == 0 else 3),
                     dict(event='stop', why='battle_over_hands_visible'), dict(event='end'))
            self.completed += 1
            self.sequence.append(self.arm.key)
            self.current = None
            if (stop and self.scenario != 'slow_stop') or self.scenario == 'dies_once' and len(self.starts) == 1:
                self.alive = False
            return
        if stop:
            self.alive = False
            return
        if self.noise and not self.noise_done:
            self.junk()
            self.noise_done = True
        path = self.filename()
        emit(path, self.header(), decision(hp=4392 if self.scenario == 'wrong_account' else 4424,
                                          xbow=self.scenario != 'missing_xbow'))
        if self.scenario == 'partial':
            emit(path, decision(3000, enemy=2))
        nav = self.logs / 'ladder_nav_20300101_000000.jsonl'
        emit(nav, dict(event='trophies', t=self.t, trophies_total=12000+self.completed*3))
        os.utime(nav, (self.t, self.t))
        self.current = (path, 0)
        if self.scenario == 'stop_ab':
            (self.output / 'STOP_AB').touch()

    def assert_restored(self):
        assert not self.alive
        for name, original in self.originals.items():
            p = self.live / name
            assert (p.read_bytes() if p.exists() else None) == original, name
        for name, data in self.protected.items():
            assert (self.live / name).read_bytes() == data, name
        assert (self.live / 'STOP').exists()
        assert not (self.output / 'RUNNING.lock').exists()
