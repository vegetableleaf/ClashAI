"""export13.py OLD_ATTACKS OLD_BUFFS NEW_ATTACKS NEW_BUFFS NEWLIST: export_incr.py (session scratchpad) plus the '_shields' rows
(H-SHIELD-3C) for the added captures, which export_incr.py does not write. Writes the added log names to NEWLIST."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, 'C:/Users/benpe/ClashBot')
os.environ.pop('PARITY_ATTACKS', None); os.environ.pop('PARITY_BUFFS', None)   # read the captures, not an export
from scratchpad.gauntlet.L74.parity import fights as F

oa, ob, na, nb, nl = sys.argv[1:6]
att = json.loads(Path(oa).read_text()); buf = json.loads(Path(ob).read_text())
births = att.pop('_births', {}); shields = att.pop('_shields', {})
p3 = {json.loads(r.read_text()).get('live_log') for r in F.p3_runs()} - {None}
# the live run is still capturing: leave out a log written to in the last 10 minutes (a match in progress)
LR = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader')
p3 = {n for n in p3 if not (LR/Path(n).name).exists() or __import__('time').time() - (LR/Path(n).name).stat().st_mtime > 600}
p2 = {json.loads(r.read_text()).get('live_log') for r in sorted(F.P2_DIR.glob('*/run.json'))} - {None}
new_att = sorted(p3 - set(att)); new_buf = sorted((p2 | p3) - set(buf))
print('attacks: reuse', len(att), 'new', len(new_att), '| buffs: reuse', len(buf), 'new', len(new_buf), flush=True)
for n in new_att:
    att[n] = F.phase3_attacks(n)
    b = F.phase3_births(n)
    if b:
        births[n] = b
    s = F.phase3_shields(n)
    if s:
        shields[n] = s
for n in new_buf:
    buf[n] = F.phase2_buffs(n)
att['_births'] = births; att['_shields'] = shields
Path(na).write_text(json.dumps(att, separators=(',', ':'))); Path(nb).write_text(json.dumps(buf))
Path(nl).write_text('\n'.join(new_att) + '\n')
print('births for', len(births), 'logs; shields for', len(shields), 'logs; wrote', na, nb)
