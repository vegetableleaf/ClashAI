"""STOP-only live icebow A/B orchestration; --dry-run is entirely offline."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LIVE = ROOT / 'scratchpad/gauntlet/L70/live'
LOGS = ROOT / 'scratchpad/gauntlet/L68/live_reader'
BASH = r'C:\Program Files\Git\usr\bin\bash.exe'


class Abort(RuntimeError):
    pass


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic(path, data):
    tmp = path.with_name(path.name + '.ab_tmp')
    tmp.write_bytes(data)
    os.replace(tmp, path)


def append(path, obj):
    with path.open('a', encoding='utf8') as f:
        f.write(json.dumps(obj, allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


@dataclass(frozen=True)
class Arm:
    key: str
    label: str
    ckpt: Path
    fast: bool
    sha: str

    @classmethod
    def parse(cls, text):
        try:
            key, label, tail = text.split(':', 2)
            path, fast = tail.rsplit(':', 1)  # preserve Windows drive colon
            if key not in ('A', 'B') or not label.strip() or fast not in ('on', 'off'):
                raise ValueError()
            p = Path(path).expanduser()
            p = (ROOT / p).resolve() if not p.is_absolute() else p.resolve()
            return cls(key, label, p, fast == 'on', sha256(p))
        except (ValueError, OSError) as e:
            raise argparse.ArgumentTypeError('arm must be A|B:label:existing-checkpoint:on|off') from e


def tower_kind(b):
    """Same coordinate filter as phase_stats: exclude non-tower card_id=-1 bodies."""
    if b.get('card_id') != -1 or b.get('side') not in (0, 1):
        return None
    x, y = b.get('x', -99999), b.get('y', -99999)
    if abs(x - 9000) < 200 and abs(y - (3000 if b['side'] == 0 else 29000)) < 200:
        return 'king'
    if min(abs(x - 3500), abs(x - 14500)) < 200 and abs(y - (6500 if b['side'] == 0 else 25500)) < 200:
        return 'princess'
    return None


def project(j):
    p = j.get('public') or {}
    # Never retain opponent hands, deck, elixir, or ability readiness.
    return {'tick': j.get('tick', 0), 'side': p.get('observer_side'),
            'bodies': [{k: b.get(k) for k in ('card_id', 'side', 'x', 'y', 'hp', 'max_hp')}
                       for b in p.get('raw_bodies', []) if tower_kind(b)],
            'cards': p.get('own_deck', p.get('own_hand', []))}


def guard(d):
    """Account check = own princess max HP 4424 on BOTH towers (main account; the bait account shows 4392). The opening
    hand is 4 of 8 cards, so X-Bow absence there is NOT evidence of a wrong deck (lead fix 10-12: it would stop ~half
    of all valid runs); the deck is reported, not enforced."""
    towers = [b for b in d['bodies'] if b['side'] == d['side'] and tower_kind(b) == 'princess']
    hp = [b['max_hp'] for b in towers]
    if len(hp) != 2 or set(hp) != {4424}:
        raise Abort(f'ACCOUNT GUARD: own princess max HP={hp} (need two 4424 = MAIN account). STOP requested; '
                    'switch MuMu to the main account.')


class Match:
    """Incremental JSONL tailer: a partial final line is retried, never consumed."""
    def __init__(self, path):
        self.path, self.offset = path, 0
        self.head = self.first = self.last = None
        self.closed = self.guarded = self.bad = False
        self.reason = None
        self.trophies = None

    def read(self):
        if self.path.stat().st_size < self.offset:
            raise Abort('Log truncated during A/B: ' + self.path.name)
        with self.path.open('rb') as f:
            f.seek(self.offset)
            while raw := f.readline():
                if not raw.endswith(b'\n'):
                    break
                self.offset = f.tell()
                try:
                    j = json.loads(raw)
                except (ValueError, UnicodeError):
                    self.bad = True
                    continue
                if self.head is None:
                    if j.get('event') != 'start':
                        self.bad = True
                    self.head = {k: j.get(k) for k in ('ckpt', 'ckpt_sha256', 'pipeline_decisions', 'dry_run')}
                ev = j.get('event')
                if ev == 'decision':
                    d = project(j)
                    if self.first is None:
                        self.first = d
                    if self.last and d['tick'] < self.last['tick']:
                        self.bad = True
                    self.last = d
                elif ev == 'stop':
                    self.reason = j.get('why')
                elif ev == 'end':
                    self.closed = True
                if isinstance(j.get('trophies_total'), (int, float)):
                    self.trophies = j['trophies_total']

    def matches(self, arm):
        h = self.head or {}
        # Missing pipeline_decisions means OFF in the current writer; missing SHA never matches.
        fast = h.get('pipeline_decisions')
        return (h.get('ckpt_sha256') == arm.sha and bool(h.get('ckpt'))
                and (fast is None or type(fast) is bool) and (fast is True) == arm.fast
                and not h.get('dry_run'))

    def outcome(self):
        if not self.closed or not self.last or self.bad:
            return None
        d = self.last
        bodies = d['bodies']
        own = sum(b['side'] == d['side'] and b['hp'] > 0 for b in bodies)
        enemy = sum(b['side'] != d['side'] and b['hp'] > 0 for b in bodies)
        early = (d['tick'] < 2400 and self.reason == 'battle_over_hands_visible'
                 and min(own, enemy) == 0 and max(own, enemy) >= 2)
        if len(bodies) < 2 or (d['tick'] < 2400 and not early):
            return None
        diff = own - enemy  # crowns taken minus crowns lost
        return {'result': 'W' if diff > 0 else 'L' if diff < 0 else 'D',
                'tower_diff': diff, 'early_terminal': early, 'stop_reason': self.reason}


def wilson(w, n):
    if not n:
        return None
    z = 1.959963984540054
    p = w / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [max(0.0, center-half), min(1.0, center+half)]


def statistics(rows):
    out = {}
    for key in ('A', 'B'):
        rs = [r for r in rows if r['arm'] == key and r.get('counted', True)]
        c = Counter(r['result'] for r in rs)
        n = c['W'] + c['L']
        tr = [r['trophies'] for r in rs if r.get('trophies') is not None]
        out[key] = dict(n=len(rs), W=c['W'], L=c['L'], D=c['D'],
                        win_rate=c['W']/n if n else None, ci95=wilson(c['W'], n),
                        trophies=tr, trophies_change=tr[-1]-tr[0] if len(tr) >= 2 else None)
    a, b = out['A'], out['B']
    if a['ci95'] and b['ci95']:
        pa, pb = a['win_rate'], b['win_rate']
        al, au = a['ci95']; bl, bu = b['ci95']
        # Newcombe independent two-proportion difference, B minus A (Wilson score intervals).
        out['difference_B_minus_A'] = dict(value=pb-pa, ci95=[
            max(-1.0, pb-pa-math.hypot(pb-bl, au-pa)),
            min(1.0, pb-pa+math.hypot(bu-pb, pa-al))])
    else:
        out['difference_B_minus_A'] = None
    return out


class RealControl:
    def __init__(self, output):
        self.output = output
        self.launcher = None
        self.env = os.environ.copy()
        for k in ('CKPT', 'LIVE_ARGS', 'LIVE_FAST', 'LIVE_EMOTES', 'LIVE_DECK', 'HAND_READER'):
            if self.env.get(k):
                raise Abort(f'Unset inherited {k} before running A/B; persisted settings must be authoritative.')
        # start_live writes these two settings; only allow identical effective values.
        if (LIVE / 'LIVE_DECK').read_bytes() != b'icebow\n':
            raise Abort('LIVE_DECK must already contain icebow with an LF newline. '
                        'A/B will not change another live setting.')
        emotes = (LIVE / 'LIVE_EMOTES').read_bytes()
        if emotes not in (b'on\n', b'off\n'):
            raise Abort('LIVE_EMOTES must already contain on or off with an LF newline.')
        self.emotes = emotes.decode().strip()
        # Import only in real mode; fake mode needs the standard library alone.
        import psutil
        self.psutil = psutil

    def running(self):
        n = int(self.launcher is not None and self.launcher.poll() is None)
        try:
            for p in self.psutil.process_iter(['name', 'cmdline']):
                try:
                    name = (p.info['name'] or '').lower()
                    if not (name.startswith('python') or name in ('bash', 'bash.exe')):
                        continue
                    if p.info['cmdline'] is None:
                        raise Abort('Cannot read a candidate live process command line; refusing restart.')
                    cl = ' '.join(p.info['cmdline']).replace('\\', '/')
                    if ('live/run_live.sh' in cl or
                        ('--ladder' in cl and ('live_play.py' in cl or 'live_play_hand_v' in cl))):
                        n += 1
                except self.psutil.NoSuchProcess:
                    continue
        except self.psutil.Error as e:
            raise Abort('Cannot establish live process state; STOP only, no restart.') from e
        return n

    def starting(self):
        return self.launcher is not None and self.launcher.poll() is None

    def command(self, arm, check=False):
        args = [BASH, str(LIVE / 'start_live.sh'), 'icebow']
        if not arm.fast:
            args.append('--no-fast-plays')
        if self.emotes == 'on':
            args.append('--emotes')
        if check:
            args.append('--check')
        return args

    def check(self, arm):
        # No timeout-based subprocess.run: it kills on timeout. Offline check gets time to finish.
        p = subprocess.run(self.command(arm, True), cwd=ROOT, env=self.env, capture_output=True)
        text = p.stdout.decode('utf8', errors='replace')
        receipts = []
        for line in text.splitlines():
            try:
                receipts.append(json.loads(line))
            except ValueError:
                pass
        return p.returncode == 0 and any(isinstance(j, dict) and j.get('check') == 'LIVE_CHECK_PASS'
                                       and j.get('sha256') == arm.sha for j in receipts)

    def start(self, arm):
        with (self.output / 'live_start.out').open('ab') as f:
            self.launcher = subprocess.Popen(self.command(arm), cwd=ROOT, env=self.env,
                                             stdout=f, stderr=f)

    def post(self, message):
        p = self.output / ('discord_' + uuid.uuid4().hex + '.txt')
        p.write_text(message, encoding='utf8')
        # Suppress child output: even an HTTP error must never expose the webhook.
        r = subprocess.run([sys.executable, str(ROOT / 'scratchpad/gauntlet/L69/discord/post.py'), str(p)],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0


class Runner:
    def __init__(self, arms, control, live=LIVE, logs=LOGS, output=HERE, block=5, total=150,
                 poll=1.0, stall=1200, grace=90, stop_timeout=2400, clock=time, now=time.time):
        self.arms, self.control = arms, control
        self.live, self.logs, self.output = live, logs, output
        self.block, self.total = block, total
        self.poll, self.stall, self.grace, self.stop_timeout = poll, stall, grace, stop_timeout
        self.clock, self.now = clock, now
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8]
        self.rows, self.matches, self.seen = [], {}, set()
        self.restarts = 0
        self.boundary_stop = False
        self.stop_overdue = False
        self.active = None
        self.controlled = False
        self.snapshots = {}
        self.output.mkdir(parents=True, exist_ok=True)

    def event(self, kind, **kw):
        append(self.output / 'events.jsonl', dict(run_id=self.run_id, t=self.now(), event=kind, **kw))

    def post(self, message):
        self.event('notification', message=message)
        print(message, flush=True)
        try:
            posted = self.control.post('[live A/B] ' + message)
        except Exception:
            posted = False  # never echo a transport exception that might contain a webhook
        if not posted:
            self.event('discord_failed')
            print('Discord post failed; report saved locally.', flush=True)

    def report(self, why):
        s = statistics(self.rows)
        self.event('report', why=why, statistics=s)
        parts = [why]
        for arm in self.arms:
            v = s[arm.key]
            ci = v['ci95']
            rate = (f"{v['win_rate']:.1%} [{ci[0]:.1%}, {ci[1]:.1%}]" if ci else 'n/a')
            tr = v['trophies']
            parts.append(f"{arm.key} {arm.label}: {v['W']}W/{v['L']}L/{v['D']}D, win {rate}; "
                         f"trophies {str(tr[0])+' -> '+str(tr[-1]) if tr else 'unavailable'}")
        diff = s['difference_B_minus_A']
        parts.append('B-A: ' + (f"{100*diff['value']:+.1f} pp "
                     f"[{100*diff['ci95'][0]:+.1f}, {100*diff['ci95'][1]:+.1f}]" if diff else 'n/a'))
        parts.append('95% Wilson/Newcombe CIs; draws excluded from win rates. Trophy reads are observations, not credited gains.')
        self.post('\n'.join(parts))

    def count(self, arm):
        return sum(r['arm'] == arm.key and r['counted'] for r in self.rows)

    def request_stop(self):
        (self.live / 'STOP').touch()

    def wait_stop(self, collect=False):
        self.request_stop()
        since = self.now()
        warned = False
        while True:
            # Reassert while a slow starter may still remove STOP. Never terminate it.
            self.request_stop()
            if collect:
                self.scan()
            try:
                running = self.control.running()
            except Abort:
                running = 1  # unknown is not safe to switch or restore
            if not running:
                if collect:
                    self.scan()
                return
            if not warned and self.now()-since >= self.stop_timeout:
                self.post('STOP wait exceeded deadline. No more starts; still waiting without killing. '
                          'Original settings backup retained until live and starter are confirmed ended.')
                self.stop_overdue = True
                warned = True
            self.clock.sleep(self.poll)

    def trophy(self, match):
        if match.trophies is not None:
            return match.trophies, 'match_log', None
        # Only reads within this block and <= match end observation; never borrow another arm's future read.
        candidates = []
        for p in self.logs.glob('ladder_nav_*.jsonl'):
            if p.stat().st_mtime < self.block_since:
                continue
            with p.open(encoding='utf8', errors='replace') as f:
                for line in f:
                    try:
                        j = json.loads(line)
                        if (j.get('event') == 'trophies' and isinstance(j.get('trophies_total'), (int, float))
                            and self.block_since <= j.get('t', 0) <= self.now()):
                            candidates.append((j['t'], j['trophies_total'], p.name))
                    except ValueError:
                        continue
        if not candidates:
            return None, None, None
        t, value, source = max(candidates)
        return value, source, t

    def scan(self):
        self.check_protected()
        if ((self.live / 'CKPT_OVERRIDE').read_text().strip() != self.active.ckpt.as_posix() or
            (self.live / 'LIVE_FAST').read_text().strip() != ('on' if self.active.fast else 'off')):
            raise Abort('An external writer changed the active arm settings; STOP requested.')
        for p in sorted(self.logs.glob('live_play_*.jsonl')):
            if p.name in self.existing:
                continue
            try:
                stamp = datetime.strptime(p.stem[len('live_play_'):len('live_play_')+15], '%Y%m%d_%H%M%S').timestamp()
            except ValueError:
                continue
            if stamp < math.floor(self.block_since):
                continue
            m = self.matches.setdefault(p.name, Match(p))
            m.read()
            # Check every new first decision, even if the arm header does not match.
            if m.first and not m.guarded:
                guard(m.first)
                m.guarded = True
                self.event('account_guard_pass', match_file=p.name)
            if not m.matches(self.active) or not m.guarded:
                continue
            out = m.outcome()
            if out and p.name not in self.seen:
                self.seen.add(p.name)
                counted = self.count(self.active) < self.total
                tr, source, tr_time = self.trophy(m)
                row = dict(run_id=self.run_id, block=self.block_index, match_file=str(p.resolve()),
                           arm=self.active.key, label=self.active.label, ckpt_sha256=self.active.sha,
                           fast=self.active.fast, counted=counted, trophies=tr,
                           trophy_source=source, trophy_time=tr_time, **out)
                append(self.output / 'results.jsonl', row)
                self.rows.append(row)
                self.progress = self.now()
                # Stop before a potentially slow Discord post at a completion boundary.
                if self.count(self.active)-self.block_before >= self.target:
                    self.request_stop()
                if counted and self.count(self.active) % 10 == 0:
                    self.report(f'{self.active.key} reached {self.count(self.active)} matches')
                if not counted:
                    self.event('overflow', match_file=p.name)
        n = self.count(self.active) - self.block_before
        pending = any(name not in self.attempt_existing and m.matches(self.active) and m.guarded and not m.closed
                      for name, m in self.matches.items())
        # STOP is read between matches. Arm it as soon as the block's final match is underway.
        if n >= self.target or (n >= self.target-1 and pending):
            self.request_stop()

    def launch(self):
        arm = self.active
        if self.stop_overdue:
            raise Abort('STOP timeout exceeded; live finally ended, but further starts are forbidden.')
        if sha256(arm.ckpt) != arm.sha:
            raise Abort(f'Checkpoint changed after arm registration: {arm.label}')
        if self.control.running():
            raise Abort('Refusing to change settings while a live process is running.')
        atomic(self.live / 'CKPT_OVERRIDE', (arm.ckpt.as_posix()+'\n').encode())
        atomic(self.live / 'LIVE_FAST', ('on\n' if arm.fast else 'off\n').encode())
        if not self.control.check(arm):
            raise Abort(f'{arm.key}: offline check did not return LIVE_CHECK_PASS with the expected SHA.')
        self.event('check_pass', arm=arm.key, ckpt_sha256=arm.sha)
        self.check_protected()
        self.attempt_existing = {p.name for p in self.logs.glob('live_play_*.jsonl')}
        self.control.start(arm)
        self.started = self.progress = self.now()
        self.event('start', arm=arm.key, restart=self.restarts)

    def check_protected(self):
        for p, original in self.protected.items():
            current = p.read_bytes() if p.exists() else None
            if current != original:
                raise Abort(f'Protected setting changed externally: {p.name}; refusing further starts.')

    def execute(self):
        lock = self.output / 'RUNNING.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as e:
            raise Abort('RUNNING.lock exists; verify previous runner has ended before removing it.') from e
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps({'pid': os.getpid(), 'run_id': self.run_id}))
        code = 0
        try:
            if (self.output / 'STOP_AB').exists():
                self.post('STOP_AB already present; no live controls changed.')
                return 0
            backup = self.output / 'backups' / self.run_id
            backup.mkdir(parents=True)
            for name in ('CKPT_OVERRIDE', 'LIVE_FAST'):
                p = self.live / name
                self.snapshots[name] = p.read_bytes() if p.exists() else None
                if self.snapshots[name] is not None:
                    (backup / name).write_bytes(self.snapshots[name])
            (backup / 'manifest.json').write_text(json.dumps({k: v is not None for k, v in self.snapshots.items()}))
            self.protected = {self.live / n: (self.live / n).read_bytes() if (self.live / n).exists() else None
                              for n in ('LIVE_OPTIONS', 'LIVE_DECK', 'LIVE_EMOTES', 'HAND_READER_ENABLED')}
            self.controlled = True
            self.event('run_start', block_size=self.block, total_per_arm=self.total,
                       arms=[dict(arm=a.key, label=a.label, ckpt=str(a.ckpt), sha256=a.sha, fast=a.fast)
                             for a in self.arms], backup=str(backup))
            self.wait_stop()
            self.block_index = 0
            while not all(self.count(a) >= self.total for a in self.arms):
                if self.boundary_stop or (self.output / 'STOP_AB').exists():
                    self.post('STOP_AB / signal: clean block boundary reached.')
                    break
                self.active = self.arms[self.block_index % 2]
                self.block_index += 1
                if self.count(self.active) >= self.total:
                    continue
                self.check_protected()
                self.block_before = self.count(self.active)
                self.target = min(self.block, self.total-self.block_before)
                self.existing = {p.name for p in self.logs.glob('live_play_*.jsonl')}
                self.matches = {}
                self.block_since = self.now()
                self.launch()
                while True:
                    self.scan()
                    if self.count(self.active)-self.block_before >= self.target:
                        self.wait_stop(collect=True)
                        break
                    elapsed = self.now()-self.started
                    dead = not self.control.running() and elapsed >= self.grace
                    stalled = self.now()-self.progress >= self.stall
                    if dead or stalled:
                        self.wait_stop(collect=True)
                        if self.count(self.active)-self.block_before >= self.target:
                            break
                        if self.restarts >= 3:
                            raise Abort('Restart limit reached: initial start plus at most 3 recovery starts; STOP left in place.')
                        self.restarts += 1
                        self.post(f'{self.active.key}: {"dead" if dead else "stalled"} supervisor; restart {self.restarts}/3.')
                        self.launch()
                    self.clock.sleep(self.poll)
                self.event('block_end', arm=self.active.key, completed=self.count(self.active)-self.block_before)
                if self.stop_overdue:
                    raise Abort('STOP timeout exceeded; originals will be restored, no further starts.')
            self.report('A/B finished' if all(self.count(a) >= self.total for a in self.arms) else 'A/B stopped')
        except (Exception, KeyboardInterrupt) as e:
            code = 1
            if self.controlled:
                self.request_stop()
            self.post(f'A/B stopped: {type(e).__name__}: {e}')
        finally:
            try:
                if self.controlled:
                    self.wait_stop()
                    for name, data in self.snapshots.items():
                        p = self.live / name
                        if data is None:
                            p.unlink(missing_ok=True)
                        else:
                            atomic(p, data)
                    self.event('restored', settings=list(self.snapshots))
                    self.post('Original CKPT_OVERRIDE and LIVE_FAST restored; live remains stopped.')
            except BaseException:
                # A crash/failed restoration leaves the lock and backup as recovery evidence.
                raise
            else:
                lock.unlink(missing_ok=True)
        return code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm', action='append', type=Arm.parse)
    p.add_argument('--block', type=int, default=5)
    p.add_argument('--total', type=int, default=150)
    p.add_argument('--dry-run', action='store_true', help='run the complete offline fake-supervisor acceptance suite')
    p.add_argument('--poll', type=float, default=1.0)
    p.add_argument('--stall-seconds', type=float, default=1200)
    args = p.parse_args()
    if args.dry_run:
        from test_live_ab import run_suite
        return run_suite('all')
    if not args.arm or len(args.arm) != 2 or {a.key for a in args.arm} != {'A', 'B'}:
        p.error('exactly one --arm A:label:ckpt:on|off and --arm B:label:ckpt:on|off are required')
    if any(not math.isfinite(v) or v <= 0 for v in (args.block, args.total, args.poll, args.stall_seconds)):
        p.error('block, total, poll and stall-seconds must be positive')
    try:
        runner = Runner(sorted(args.arm, key=lambda a: a.key), RealControl(HERE),
                        block=args.block, total=args.total, poll=args.poll, stall=args.stall_seconds)
        def stop_at_boundary(signum, frame):
            runner.boundary_stop = True
        signal.signal(signal.SIGINT, stop_at_boundary)
        signal.signal(signal.SIGTERM, stop_at_boundary)
        return runner.execute()
    except (Abort, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
