"""ClashAI daily report helper -- the scheduled task's ONLY shell command, so one allow rule covers a whole run:
    Bash(icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/daily/daily.py *)

  daily.py gather        today's live facts (ladder outcomes, models, supervisor tail, live running?, git log)
  daily.py post <<'EOF'  report text on stdin -> scratchpad/gauntlet/L73/daily/<date>.txt -> Discord (retry once after 60 s)
Read-only apart from that one text file. Never prints the webhook URL (post.py reads it)."""
import datetime as dt, glob, json, subprocess, sys, time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LR = REPO / 'scratchpad/gauntlet/L68/live_reader'
PY = str(REPO / 'icebow/.venv/Scripts/python.exe')
TODAY = dt.date.today()


def gather():
    out = []
    ev = []
    for f in glob.glob(str(LR / 'ladder_nav_*.jsonl')):
        for line in open(f, encoding='utf-8', errors='replace'):
            if '"event": "outcome"' in line:
                d = json.loads(line)
                if dt.datetime.fromtimestamp(d['t']).date() == TODAY:
                    ev.append(d)
    ev.sort(key=lambda d: d['t'])
    w = sum(d['won'] for d in ev)
    out.append(f"ladder today: {len(ev)} matches, {w} W - {len(ev) - w} L"
               + (f" ({w / len(ev):.0%}), trophies {sum(d['trophies_delta'] for d in ev):+d}" if ev else ' -- no live matches today'))
    if ev:
        s = ev[-1]['state']
        out.append(f"all-time W/L after the last match: {s.get('W')}-{s.get('L')}; last match {dt.datetime.fromtimestamp(ev[-1]['t']):%H:%M}")
    models = Counter()
    for f in sorted(glob.glob(str(LR / f'live_play_{TODAY:%Y%m%d}_*.jsonl'))):
        with open(f, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if line.startswith('{"event": "start"'):
                    models[Path(json.loads(line).get('ckpt') or '?').stem] += 1
                    break
    out.append('models (live_play logs today): ' + (', '.join(f'{k} x{v}' for k, v in models.items()) or 'none'))
    sup = (REPO / 'scratchpad/gauntlet/L70/live/supervisor.log')
    if sup.exists():
        out.append('supervisor.log tail:\n  ' + '\n  '.join(sup.read_text(encoding='utf-8', errors='replace').splitlines()[-12:]))
    try:
        import psutil
        n = sum('live_play.py' in ' '.join(p.info['cmdline'] or []) for p in psutil.process_iter(['cmdline']))
        out.append(f"live running now: {'yes' if n else 'NO'} ({n} live_play processes)")
    except Exception as e:                     # never fail the report over the process check
        out.append(f'live running now: unknown ({e})')
    out.append('git log since midnight:\n' + subprocess.run(['git', 'log', '--since=midnight', '--oneline'], cwd=REPO,
                                                            capture_output=True, text=True).stdout)
    print('\n'.join(out))


def post():
    text = sys.stdin.read().strip()
    assert text, 'empty report on stdin'
    p = Path(__file__).with_name(f'{TODAY:%Y-%m-%d}.txt')
    p.write_text(text + '\n', encoding='utf-8')
    for attempt in (1, 2):
        r = subprocess.run([PY, str(REPO / 'scratchpad/gauntlet/L69/discord/post.py'), str(p)], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip()[-300:])
        if r.returncode == 0:
            return
        if attempt == 1:
            time.sleep(60)
    sys.exit(f'post failed twice; the report is saved at {p}')


if __name__ == '__main__':
    {'gather': gather, 'post': post}.get(sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
