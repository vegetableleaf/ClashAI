"""Freeze main-account Icebow truth using the existing phase_stats selection rule.

No runtime/model imports. Draws remain in the denominator (a win is exactly 1).
Metadata is an allowlist; no opponent hand/deck/elixir is retained.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
META = ('tau', 'extrapolate', 'opp_counter', 'anti_leak', 'own_effects',
        'afford_ticks', 'early_release_margin', 'fast_input', 'tap_gap_ms',
        'hero_ability_spec', 'iw_press_pstar', 'identity_ext', 'follow_up_taps',
        'pipeline_tau_delta', 'decision_options', 'feature_version')


def load_phase_stats():
    # Lazy: pod workers/scoring do not need the live-log analysis dependencies.
    path = HERE.parent / 'phase_stats/phase_stats.py'
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('livecal_phase_stats', path)
    module = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
        sys.path.pop(0)
    return module


def wilson(w, n):
    z = 1.96
    mid = (w/n + z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(w/n*(1-w/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [mid-half, mid+half]


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def relative_checkpoint(raw):
    p = str(raw or '').replace('\\', '/')
    i = p.lower().find('icebow/data/')
    return p[i:] if i >= 0 else p


def family(path):
    name = Path(path).name
    if name == 'rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt':
        return 'old'
    if name == 'rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt':
        return 'E4'
    return Path(path).stem


def header(path):
    with path.open(encoding='utf8') as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('event') == 'start':
                return {k: row[k] for k in ('ckpt', 'ckpt_sha256', 'pipeline_decisions', 'live_options', *META) if k in row}
    return {}


def era_for(h):
    lo = h.get('live_options') or {}
    # Hash effective recorded settings plus the applied options, excluding paths/messages/random seeds.
    settings = {k: h[k] for k in META if k in h}
    settings.pop('pipeline_tau_delta', None)  # fast dimension is separate
    applied = dict(lo.get('from_file') or {}) if lo.get('status') == 'applied' else {}
    applied.pop('pipeline_decisions', None)
    applied.pop('pipeline_tau_delta', None)
    payload = {'settings': settings, 'applied_options': applied, 'status': lo.get('status', 'not_recorded')}
    return hashlib.sha256(canonical(payload).encode()).hexdigest()[:10], payload


def build_truth(paths, root=ROOT, min_n=30):
    PS = load_phase_stats()
    rule_sha = digest(Path(PS.__file__))
    started = datetime.now(timezone.utc).isoformat()
    groups, excluded, receipts = {}, Counter(), []
    for path in sorted(map(Path, paths)):
        before = path.stat()
        data, reason = PS.read_live(path)
        if reason:
            excluded[reason] += 1
            continue
        h = header(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            excluded['changed_while_reading'] += 1
            continue
        ck = relative_checkpoint(h.get('ckpt'))
        sha = h.get('ckpt_sha256')
        fast = bool(h.get('pipeline_decisions', False))  # same legacy missing=false rule as phase_stats
        era, payload = era_for(h)
        key = (ck, sha, fast, era, h.get('pipeline_tau_delta', 0))
        gid = hashlib.sha256(canonical(key).encode()).hexdigest()[:12]
        if gid not in groups:
            groups[gid] = dict(id=gid, checkpoint=ck, checkpoint_sha256=sha, family=family(ck), fast=fast,
                               era=era, era_metadata=payload, settings={k: h[k] for k in META if k in h},
                               fast_flag_recorded=0, n=0, wins=0, losses=0, draws=0, early_terminal=0,
                               first_log=path.name, last_log=path.name)
        g = groups[gid]
        tw = PS.towers(data['decisions'][-1])
        took = 3 - sum(v > 0 for k, v in tw.items() if k.startswith('enemy_'))
        lost = 3 - sum(v > 0 for k, v in tw.items() if k.startswith('own_'))
        outcome = 'wins' if took > lost else 'losses' if took < lost else 'draws'
        g['n'] += 1
        g[outcome] += 1
        g['fast_flag_recorded'] += 'pipeline_decisions' in h
        g['early_terminal'] += data['early_terminal']
        g['last_log'] = path.name
        receipts.append(dict(log=path.name, sha256=data['sha256'], bytes=data['bytes'], group=gid, outcome=outcome))
    files = {}
    for g in groups.values():
        g.update(win_rate=g['wins']/g['n'], ci95=PS.wilson(g['wins'], g['n'])['ci95'], reportable=g['n'] >= min_n)
        ck = g['checkpoint']
        path = root / ck
        exists = ck.startswith('icebow/data/') and path.is_file()
        if ck not in files:
            files[ck] = dict(path=ck, exists=exists, bytes=path.stat().st_size if exists else None,
                             sha256=digest(path) if exists else None)
        g['checkpoint_exists'] = exists
        g['checkpoint_verified'] = exists and (g['checkpoint_sha256'] is None or g['checkpoint_sha256'] == files[ck]['sha256'])
        g['identity_note'] = 'logged SHA verified' if g['checkpoint_sha256'] else 'path only; historical bytes unproven'
    return dict(schema=1, min_n=min_n, started_utc=started, completed_utc=datetime.now(timezone.utc).isoformat(),
                rule_source='scratchpad/gauntlet/L74/phase_stats/phase_stats.py',
                rule_sha256=rule_sha, groups=list(groups.values()), files=list(files.values()),
                accepted=len(receipts), excluded=dict(excluded), matches=receipts)


def table(truth):
    lines = ['Main-account Icebow; wins / all selected matches; 95% Wilson CI.',
             'Missing pipeline_decisions is fast-off (phase_stats convention); recorded-count is retained in JSON.',
             'Group | checkpoint | fast | era | n | W/L/D | win % [95% CI] | bytes verified']
    for g in truth['groups']:
        if g['reportable'] or g['family'].startswith('adapt_'):
            lo, hi = g['ci95']
            lines.append(f"{g['id']} | {Path(g['checkpoint']).name} | {g['fast']} | {g['era']} | {g['n']} | "
                         f"{g['wins']}/{g['losses']}/{g['draws']} | {100*g['win_rate']:.1f} [{100*lo:.1f}, {100*hi:.1f}] | "
                         f"{g['checkpoint_verified']}{' (small n; report only)' if not g['reportable'] else ''}")
    lines += [f"Accepted: {truth['accepted']}; exclusions: {truth['excluded']}", '', 'Descriptive family totals (mixed eras):']
    totals = defaultdict(Counter)
    for g in truth['groups']:
        for k in ('n', 'wins', 'losses', 'draws'):
            totals[g['family'], g['fast']][k] += g[k]
    for (name, fast), c in totals.items():
        lo, hi = wilson(c['wins'], c['n'])
        lines.append(f"{name} fast={fast}: {c['wins']}/{c['losses']}/{c['draws']}, n={c['n']}, "
                     f"{100*c['wins']/c['n']:.1f}% [{100*lo:.1f}, {100*hi:.1f}]")
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--logs', type=Path, default=ROOT/'scratchpad/gauntlet/L68/live_reader')
    ap.add_argument('--out', type=Path, default=HERE/'truth.json')
    a = ap.parse_args()
    truth = build_truth(a.logs.glob('live_play_*.jsonl'))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(truth, indent=2), encoding='utf8')
    a.out.with_suffix('.txt').write_text(table(truth), encoding='utf8')
    print(table(truth))


if __name__ == '__main__':
    main()
