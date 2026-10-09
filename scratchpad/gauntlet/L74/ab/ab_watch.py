"""Owner 2026-10-08 21:4x: live A/B of the Hero IW ability fix. Arm OFF = the run the owner started at 21:20 (bundle 2,
--hero-ability-spec off); after 20 completed matches: stop between matches (STOP file), restart the supervisor with
LIVE_ARGS="--hero-ability-spec supplement" for 20 more, then stop and leave live OFF. Discord note at each step.
Never kills anything: stops only through the supervisor's own STOP file."""
import glob, json, os, subprocess, sys, time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[4]
L = REPO / 'scratchpad/gauntlet/L70/live'
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
STATE = Path(__file__).with_name('ab_state.json')
OUT = Path(__file__).with_name('ab_watch.out')
BASH = r'C:\Program Files\Git\usr\bin\bash.exe'
PY = str(REPO / 'icebow/.venv/Scripts/python.exe')
N = 20
T0 = '20261008_212000'          # arm OFF began with the supervisor started 21:20:12


def say(msg):
    line = time.strftime('%H:%M:%S ') + msg
    with open(OUT, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    try:
        p = Path(__file__).with_name('_msg.txt')
        p.write_text('ClashAI live A/B: ' + msg, encoding='utf-8')
        subprocess.run([PY, str(REPO / 'scratchpad/gauntlet/L69/discord/post.py'), str(p)], timeout=60,
                       capture_output=True)
    except Exception:
        pass


def live_running():
    n = 0
    for p in psutil.process_iter(['cmdline']):
        cl = ' '.join(p.info.get('cmdline') or [])
        if ('live_play.py' in cl and '--ladder' in cl) or 'live/run_live.sh' in cl:
            n += 1
    return n


def matches(spec, since):
    """Completed live matches (log has an 'end' event) started at/after `since` with hero_ability_spec == spec."""
    done = []
    for f in sorted(glob.glob(str(LOGS / 'live_play_2026*.jsonl'))):
        stamp = os.path.basename(f)[len('live_play_'):-len('.jsonl')]
        if stamp < since:
            continue
        start, end = None, False
        try:
            for line in open(f, encoding='utf-8', errors='replace'):
                if '"event": "start"' in line and start is None:
                    start = json.loads(line)
                elif '"event": "end"' in line:
                    end = True
        except OSError:
            continue
        if start is not None and end and (start.get('hero_ability_spec') or 'off') == spec:
            done.append(os.path.basename(f))
    return done


def stop_and_wait(timeout_s=1800):
    (L / 'STOP').touch()
    t = time.time()
    while live_running() and time.time() - t < timeout_s:
        time.sleep(15)
    return not live_running()


def main():
    st = json.loads(STATE.read_text()) if STATE.exists() else {'phase': 'off'}
    say(f"watcher up, phase {st['phase']}")
    while True:
        if st['phase'] == 'off':
            got = matches('off', T0)
            if len(got) >= N:
                say(f"arm OFF done ({len(got)} matches); stopping between matches to flip the Hero IW fix ON")
                if not stop_and_wait():
                    say('live did not stop within 30 min -- watcher giving up, nothing restarted'); return
                (L / 'STOP').unlink(missing_ok=True)
                env = dict(os.environ, LIVE_ARGS='--hero-ability-spec supplement')
                subprocess.Popen([BASH, str(L / 'run_live.sh')], cwd=str(REPO), env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                st = {'phase': 'on', 'on_since': time.strftime('%Y%m%d_%H%M%S'), 'off_matches': got}
                STATE.write_text(json.dumps(st))
                say(f"arm ON started at {st['on_since']} (--hero-ability-spec supplement)")
        elif st['phase'] == 'on':
            got = matches('supplement', st['on_since'])
            if len(got) >= N:
                say(f"arm ON done ({len(got)} matches); stopping live (left OFF for the owner)")
                stop_and_wait()
                st['phase'] = 'done'; st['on_matches'] = got
                STATE.write_text(json.dumps(st))
                say('A/B complete: 20 OFF + 20 ON; live is stopped (STOP file present)')
                return
            if not live_running():
                time.sleep(120)
                if not live_running() and not (L / 'STOP').exists():
                    say('arm ON: live is not running (supervisor gave up?) -- watcher waiting; owner may restart')
        time.sleep(30)


if __name__ == '__main__':
    main()
