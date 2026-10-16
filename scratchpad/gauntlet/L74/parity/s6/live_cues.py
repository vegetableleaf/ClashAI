"""Live-side cue fields for S6, built from the reader's own blocks exactly as READER_STREAM_SPEC.md section 5 maps them
(this is the mapping the future pipeline/live_unit_state.py would use), plus the SIM-side reduction of one extract() unit
to the same compact fields. Same keys on both sides:
  st state, ch charging, hide, tg target (live body id / None / 'unlisted'), ph phase, fr frac, pg progress_ms,
  ld load_ms, hs hit_speed_ms, S [stunned, frozen, slowed, raged, taunted, invisible, shielded], sf slow_frac,
  bf [[buff name, remaining ms, frac]]
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
STATE = {0: 'idle', 1: 'moving', 2: 'engaged', 3: 'jumping', 4: 'deploying', 5: 'jumping', 6: 'tunnelling',
         10: 'casting', 11: 'deploying'}
CUES, DEFS = {}, {}
HIT_WINDOW = 100
SENT = 900_000
ORDER = ('stunned', 'frozen', 'slowed', 'raged', 'taunted', 'invisible', 'shielded')


def captures(stem):
    runs = sorted((ROOT / 'icebow/data/p3_captures').glob('*/run.json')) + \
        sorted((ROOT / 'scratchpad/gauntlet/L70/reader/re_phase3').glob('p3_*/run.json')) +         sorted((ROOT / 'scratchpad/gauntlet/L70/reader/re_phase2/validation').glob('p2_*/run.json'))
    for run in runs:
        try:
            if json.loads(run.read_text()).get('live_log') == stem + '.jsonl':
                return run.parent / 'frames.jsonl'
        except ValueError:
            pass


def _ingest(tick, p2, p3):
    row = {}
    for u in p2.get('units', []):
        row[u['generation']] = dict(name=u['name'], buffs=u['buffs'], att=None, defid=None, why=None, at=p3 is not None)
    for b in (p3 or {}).get('bodies', []):
        r = row.setdefault(b['generation'], dict(name=None, buffs=[], att=None, defid=None, why=None))
        r.update(att=b.get('attack'), defid=b.get('definition_id'), why=b.get('null_reason'))
    for d in (p3 or {}).get('defs') or []:
        DEFS[d['definition_id']] = d
    CUES[tick] = row


def load(stem):
    """Index {tick: {generation: cue row}} from the live log's inline blocks (merged reader) when present, else from
    the phase-3 capture that names the log (exact tick only). Returns (source, frames)."""
    CUES.clear(); DEFS.clear()
    live = ROOT / 'scratchpad/gauntlet/L68/live_reader' / (stem + '.jsonl')
    n = 0
    with open(live, 'rb') as f:
        for raw in f:
            if b'"cues_defs"' in raw[:40]:
                for d in json.loads(raw)['defs']:
                    DEFS[d['definition_id']] = d
            elif b'"frame"' in raw[:40] and b'"phase3"' in raw:
                j = json.loads(raw)
                p2, p3 = j.get('phase2'), j.get('phase3')
                if p2 and p3 and p2.get('valid') and p3.get('valid') and not j.get('cues_degraded'):
                    _ingest(j['tick'], p2, p3)
                    n += 1
    if n:
        return 'live_log_inline', n
    cap = captures(stem)
    if cap is None:
        return 'none', 0
    with open(cap, 'rb') as f:
        for raw in f:
            j = json.loads(raw)
            p2, p3 = j.get('phase2'), j.get('phase3')
            if p2 and p2.get('valid') and (p3 is None or p3.get('valid')):
                _ingest(j['game_tick'], p2, p3)
                n += 1
    return 'capture', n


def _table():
    import royalesim
    from pipeline import sim_unit_state as U
    return U._tbl(royalesim)


def buff_status(b):
    """Effect words of one live buff: the sim_unit_state._statuses rule with the multipliers read from the buff's config."""
    cfg, low = b.get('config') or {}, b['name'].lower()
    spd, hsp = cfg.get('SpeedMultiplier') or 0, cfg.get('HitSpeedMultiplier') or 0
    out = set()
    if spd <= -100 or hsp <= -100:
        out.add('frozen')
    elif spd < 0 or hsp < 0:
        out.add('slowed')
    if spd > 0 or hsp > 0 or 'rage' in low:
        out.add('raged')
    for word, tag in (('taunt', 'taunted'), ('invisib', 'invisible'), ('stun', 'stunned'), ('shield', 'shielded'),
                      ('fortify', 'shielded')):
        if word in low:
            out.add(tag)
    if cfg.get('Invisible'):
        out.add('invisible')
    if cfg.get('Shield') or b.get('shield_value_raw'):
        out.add('shielded')
    return out


def live_cue(b, prev, tick, cue, gen2id, catalog, simunit=None):
    T = _table()
    name = (catalog.get(b['card_id']) or {}).get('display_name')
    ct = T['char'].get(name) or (T['char'].get(simunit['name']) if simunit else None) or {}
    if b['tower']:
        ct = T['char'].get('KingTower' if b['id'].endswith('K') else 'PrincessTower', {})
    raw = b.get('state')
    r = dict(raw=raw, st=STATE.get(raw, 'raw%s' % raw), ch=None, hide=None, tg=None, ph=None, fr=None, pg=None,
             ld=None, hs=None, S=None, sf=None, bf=None, cue=False, at=False)
    if ct.get('hides_when_not_attacking'):
        r['hide'] = {0: 'hidden', 2: 'up'}.get(raw)
    # charging: speed >= 1.6 x walk over two consecutive frames (READER_VALIDATION_1016)
    if prev is not None and ct.get('speed') and raw == 1 and not b['tower']:
        pt, pb = prev
        dt = tick - pt
        if 0 < dt <= 4:
            v = ((b['x'] - pb['x']) ** 2 + (b['y'] - pb['y']) ** 2) ** .5 / dt
            r['ch'] = v >= 1.6 * ct['speed'] * 59 / 60
    c = cue.get(b['gen']) if cue else None
    if c is None:
        return r
    r['cue'] = True
    r['at'] = c.get('at', True)
    att = c['att']
    d = DEFS.get(c['defid']) or {}
    hs = d.get('HitSpeed') or None
    r['hs'] = hs
    if att is None or att.get('target_gen') is None:
        r['tg'] = None
    else:
        r['tg'] = gen2id.get(att['target_gen'], 'unlisted')
    prog = att['progress_raw'] if att else 0
    r['pg'], r['ld'] = prog, (att['load_raw'] if att else 0)
    if r['tg'] is None or prog <= 0:
        r['ph'] = 'idle'
    else:
        r['ph'] = 'hit' if hs and prog % hs < HIT_WINDOW else 'windup'
    r['fr'] = round(prog % hs / hs, 3) if hs and r['ph'] != 'idle' else None
    S, bf, sf = dict.fromkeys(ORDER, False), [], None
    for bu in c['buffs']:
        dur, rem = bu['duration_ms_raw'], bu['remaining_ms_raw']
        frac = None if rem >= SENT or not dur else round(min(1.0, rem / dur), 3)
        for tag in buff_status(bu):
            S[tag] = True
            if tag == 'slowed' and frac is not None:
                sf = max(sf or 0, frac)
        bf.append([bu['name'], rem, frac])
    r['S'], r['sf'], r['bf'] = [S[k] for k in ORDER], sf, bf
    return r


def sim_cue(u, uid2id, inv):
    a, s = u['attack'], u['status']
    tid = uid2id.get(a['target'])
    return dict(st=u['state'], ch=bool(u['charging']), chf=u['charge_frac'], hide=u['hide'],
                tg=(inv.get(tid, tid) if tid else None), ph=a['phase'], fr=a['frac'], pg=a['progress_ms'],
                ld=a['load_ms'], hs=a['hit_speed_ms'], S=[s[k] for k in ORDER], sf=s['slow_frac'],
                bf=[[x['name'], x['ms'], x['frac']] for x in u['buffs']])
