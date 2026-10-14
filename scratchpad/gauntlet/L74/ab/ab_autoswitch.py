"""After a live A/B ends, put the higher-scoring arm live (owner rule 2026-10-13).

Waits for live_ab.py's RUNNING.lock to go (the runner restores the pre-A/B model and leaves live STOPPED), then:
- both arms reached --total -> the higher win rate (W/(W+L)) goes live; an exact tie keeps B (the old model, which
  has the long live record);
- anything else (STOP_AB, abort, crash, lock left behind) -> no switch, Discord alert only.
Switch = back up CKPT_OVERRIDE, write the winner, start_live --check (sha must match), start live, then account-guard
the first match (two own princesses at max HP 4424 = MAIN account); a wrong account -> STOP + alert.

  python ab_autoswitch.py --run-id ID --arm A:label:ckpt:off --arm B:label:ckpt:off [--total 150]
  python ab_autoswitch.py --selftest
"""
import argparse
import dataclasses
import json
import shutil
import sys
import time

from live_ab import HERE, LIVE, LOGS, Abort, Arm, Match, RealControl, atomic, guard, statistics


def say(msg):
    print(time.strftime('%Y-%m-%d %H:%M:%S ') + msg, flush=True)


def decide(rows, total):
    """Winning arm key, or None when the A/B did not complete."""
    if any(sum(r['arm'] == k and r['counted'] for r in rows) < total for k in 'AB'):
        return None
    s = statistics(rows)
    return 'A' if s['A']['win_rate'] > s['B']['win_rate'] else 'B'


def with_extra(options, extra):
    """LIVE_OPTIONS bytes plus an arm's flags, exactly as live_ab.Runner.options_for writes them."""
    return options.rstrip(b'\r\n') + (b' ' + extra.encode() if extra else b'') + b'\n'


def summary(rows):
    s = statistics(rows)
    out = [f"{k}: {s[k]['W']}W/{s[k]['L']}L/{s[k]['D']}D = {s[k]['win_rate']:.1%} "
           f"[{s[k]['ci95'][0]:.1%}, {s[k]['ci95'][1]:.1%}]" for k in 'AB' if s[k]['ci95']]
    d = s['difference_B_minus_A']
    if d:
        out.append(f"B-A {100*d['value']:+.1f} pp [{100*d['ci95'][0]:+.1f}, {100*d['ci95'][1]:+.1f}]")
    return '; '.join(out)


def wait_runner(poll):
    lock = HERE / 'RUNNING.lock'
    import psutil
    while lock.exists():
        try:
            pid = json.loads(lock.read_text())['pid']
        except (OSError, ValueError, KeyError):
            pid = None  # being written or removed; look again
        if pid is not None and not psutil.pid_exists(pid):
            time.sleep(poll)  # the runner unlinks the lock as its very last step; allow for that
            if lock.exists():
                return False  # runner gone, lock left = crashed/failed restore: a human must look
        time.sleep(poll)
    return True


def account_check(ctl, arm, before, wait_s, poll):
    """Guard the first new match of this arm; True = main account, False = stopped, None = no match seen."""
    deadline = time.time() + wait_s
    seen = {}
    while time.time() < deadline:
        for p in sorted(LOGS.glob('live_play_*.jsonl')):
            if p.name not in before:
                seen.setdefault(p.name, Match(p)).read()
        for m in seen.values():
            if m.head and m.matches(arm) and m.first:
                try:
                    guard(m.first)
                    return True
                except Abort as e:
                    (LIVE / 'STOP').touch()
                    ctl.post(f':rotating_light: [A/B auto-switch] {e} Live STOP set.')
                    say(str(e))
                    return False
        time.sleep(poll)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run-id')
    ap.add_argument('--arm', action='append', type=Arm.parse)
    ap.add_argument('--arm-extra', action='append', default=[], metavar='KEY=FLAGS',
                    help="the same per-arm LIVE_OPTIONS flags given to live_ab.py; a winner's flags go live with it")
    ap.add_argument('--total', type=int, default=150)
    ap.add_argument('--poll', type=float, default=60)
    ap.add_argument('--guard-wait', type=float, default=2700, help='seconds to wait for the first match')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run_id or not a.arm or sorted(x.key for x in a.arm) != ['A', 'B']:
        ap.error('--run-id and one --arm A:... and one --arm B:... are required')
    extra = dict(e.split('=', 1) for e in a.arm_extra)
    arms = {x.key: dataclasses.replace(x, extra=extra.get(x.key, '').strip()) for x in a.arm}
    say(f'watching run {a.run_id}; A={arms["A"].ckpt.name} B={arms["B"].ckpt.name}')

    ok = wait_runner(a.poll)
    rows = [json.loads(l) for l in (HERE / 'results.jsonl').read_text(encoding='utf8').splitlines()
            if l.strip() and json.loads(l).get('run_id') == a.run_id]
    ctl = RealControl(HERE)
    win = decide(rows, a.total) if ok else None
    if win is None:
        why = 'RUNNING.lock left by a dead runner' if not ok else 'A/B ended before both arms reached ' + str(a.total)
        ctl.post(f':rotating_light: [A/B auto-switch] NO switch: {why}. {summary(rows)}. Live left as the runner '
                 'left it (stopped); a human decides.')
        say('no switch: ' + why)
        return 1
    if ctl.running():
        ctl.post('[A/B auto-switch] NO switch: a live process is already running; nothing changed.')
        say('live already running; no switch')
        return 1

    arm = arms[win]
    ckpt = LIVE / 'CKPT_OVERRIDE'
    backup = LIVE / 'CKPT_OVERRIDE.pre_ab_autoswitch_backup'
    shutil.copyfile(ckpt, backup)
    atomic(ckpt, (arm.ckpt.as_posix() + '\n').encode())
    opts, opts_backup = LIVE / 'LIVE_OPTIONS', LIVE / 'LIVE_OPTIONS.pre_ab_autoswitch_backup'
    if arm.extra:                                       # a flag arm (e.g. --iw-press never): its flags go live too
        shutil.copyfile(opts, opts_backup)
        atomic(opts, with_extra(opts.read_bytes(), arm.extra))
    if not ctl.check(arm):
        shutil.copyfile(backup, ckpt)
        if arm.extra:
            shutil.copyfile(opts_backup, opts)
        ctl.post(f':rotating_light: [A/B auto-switch] --check FAILED for {arm.key} {arm.label}; CKPT_OVERRIDE '
                 'restored, live stays stopped.')
        say('check failed; restored')
        return 1
    before = {p.name for p in LOGS.glob('live_play_*.jsonl')}
    ctl.start(arm)
    say(f'started live on {arm.key} {arm.label} ({arm.ckpt})')
    ctl.post(f'[A/B auto-switch] A/B finished. {summary(rows)}. Higher arm {arm.key} ({arm.label}) is now LIVE: '
             f'{arm.ckpt.name} sha {arm.sha[:8]}, fast {"on" if arm.fast else "off"}. 150/arm resolves ~+-11 pp, so a '
             f'gap inside that is not established. Undo: copy {backup.name} over CKPT_OVERRIDE' + (f' and {opts_backup.name} over LIVE_OPTIONS' if arm.extra else '') + ' and restart.')
    res = account_check(ctl, arm, before, a.guard_wait, 15)
    if res is None:
        ctl.post(f':rotating_light: [A/B auto-switch] live started but no {arm.key} match seen in '
                 f'{a.guard_wait/60:.0f} min; account not verified.')
    elif res:
        ctl.post('[A/B auto-switch] first match passed the account guard (main account, towers 4424).')
    say(f'account check: {res}')
    return 0 if res else 1


def selftest():
    def rows(aw, al, bw, bl):
        return ([dict(arm='A', counted=True, result=r) for r in 'W'*aw + 'L'*al] +
                [dict(arm='B', counted=True, result=r) for r in 'W'*bw + 'L'*bl])
    assert decide(rows(90, 60, 80, 70), 150) == 'A'
    assert decide(rows(70, 80, 80, 70), 150) == 'B'
    assert decide(rows(75, 75, 75, 75), 150) == 'B'          # exact tie keeps the old model
    assert decide(rows(90, 59, 80, 70), 150) is None          # A one short: no switch
    assert decide(rows(12, 9, 7, 13), 150) is None            # stopped early
    assert decide(rows(90, 60, 80, 70) + [dict(arm='A', counted=False, result='W')] * 5, 150) == 'A'
    assert with_extra(b'--a 1\r\n', '--iw-press never') == b'--a 1 --iw-press never\n'
    assert with_extra(b'--a 1\n', '') == b'--a 1\n'
    print('selftest OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
