"""SME-FRESH: freeze the held-out match list. Ranked battle-log entries whose live log STARTS at or after CUT (EDT), each paired with the
live log that played it by extract.batch's rule (battle end 60..600 s after the log start, nearest). Writes one TSV row per
battle: match, battleTime, opponent tag (public), live-log sha256, battle-entry sha256 (canonical JSON), phase-2 build.
    icebow/.venv/Scripts/python.exe -I freeze.py 20261028_0000 OUT.tsv"""
import datetime as dt, hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'extract'))
import extract  # noqa: E402

cut = dt.datetime.strptime(sys.argv[1], '%Y%m%d_%H%M') + dt.timedelta(hours=4)      # EDT -> UTC
logs = [p for p in extract.LIVE.glob('live_play_2026*.jsonl') if re.match(r'live_play_\d{8}_\d{6}\.jsonl$', p.name)]
rows = []
for b in extract.battles():
    end = dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S')
    if end < cut:
        continue
    c = [((end - extract.log_start(p)).total_seconds(), p) for p in logs]
    c = [x for x in c if 60 <= x[0] <= 600]
    p = min(c, key=lambda x: x[0])[1] if c else None
    if p is None or extract.log_start(p) < cut:          # "played after the cut": the log (match start) too, not only its end
        print("excluded", b["battleTime"], p.stem if p else "no_live_log"); continue
    build = None
    if p:
        for line in open(p, 'rb'):
            if b'"phase2"' in line and b'"build"' in line:
                m = re.search(rb'"build":\s*(\d+)', line)
                if m:
                    build = int(m.group(1)); break
    rows.append([p.stem if p else '-', b['battleTime'], b['opponent'][0]['tag'],
                 hashlib.sha256(p.read_bytes()).hexdigest() if p else '-',
                 hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest(), str(build)])
with open(sys.argv[2], 'w', newline='\n') as f:
    f.write('# match\tbattle_time\topp_tag\tlive_sha256\tbattle_sha256\tbuild\n')
    for r in rows:
        f.write('\t'.join(r) + '\n')
print(len(rows), 'battles;', sum(r[0] != '-' for r in rows), 'with a live log')
