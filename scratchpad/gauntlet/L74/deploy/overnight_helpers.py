"""Pure helpers for overnight_orchestrator.sh (no Claude, no network). Every subcommand prints ONE JSON line.
  verdict SUMMARY          -> {verdict: candidate|not_candidate|failed|missing, rule: c|a|b|none, gates: [...]}
  adapt SUMMARY            -> {verdict: pass|nopass|failed|missing, n, delta, lo, hi}
  nextparams JSON RULE     -> {params: {...}, args: "--epochs ..."}      (JSON = previous attempt's params, '{}' = base)
  count LOGDIR SINCE SHA [N]  -> completed live matches since SINCE (file stamp) run with checkpoint sha SHA
  running                  -> {running: n}  (live supervisor / ladder live_play processes, same test as ab_watch)
  fakelive LOGDIR SHA N    -> writes N fake match logs (dry-run only)
  selftest
"""
import glob, json, os, re, sys

BASE = dict(epochs=5, lr=1e-4, kl=100.0, cell=False)      # train_pending defaults = the TORNADO config
PRO_TORNADO_MIX = 0.119                                  # pinned pro second-card Tornado share (README gates)


def _read(p):
    try:
        return open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return None


def gates(text):
    """[(label, non_inferior, tornado_ok)] from the 'fixed-live ... non-inferior=X; Tornado gate=Y' lines."""
    out, label = [], None
    for line in text.splitlines():
        m = re.match(r'^(\w+_(?:on|off)): paired n=', line)
        if m:
            label = m.group(1)
            continue
        m = re.search(r'non-inferior=(True|False); Tornado gate=(True|False)', line)
        if m and label:
            out.append((label, m.group(1) == 'True', m.group(2) == 'True'))
            label = None
    return out


def verdict(path):
    t = _read(path)
    if t is None or not t.strip():
        return dict(verdict='missing', rule='none', gates=[])
    first = t.splitlines()[0].strip()
    g = gates(t)
    gl = [f"{l}: non_inferior={ni} tornado_ok={tk}" for l, ni, tk in g]
    if re.fullmatch(r'VERDICT:\s*candidate', first):
        return dict(verdict='candidate', rule='none', gates=gl)
    if re.fullmatch(r'VERDICT:\s*not candidate', first):
        off_bad = any(l.endswith('_off') and not ni for l, ni, _ in g)
        tor_bad = any(l.endswith('_on') and not tk for l, _, tk in g)
        on_bad = any(l.endswith('_on') and not ni for l, ni, _ in g)
        rule = 'c' if off_bad else 'a' if tor_bad else 'b' if on_bad else 'none'    # first match in order (c), (a), (b)
        return dict(verdict='not_candidate', rule=rule, gates=gl)
    return dict(verdict='failed', rule='none', gates=gl, first=first[:200])


def nextparams(prev, rule):
    p = dict(BASE, **prev)
    if rule == 'a':                                        # Tornado share still too high: more training, stronger head step
        p['epochs'] *= 2; p['lr'] *= 2
    elif rule == 'c':                                      # ordinary play hurt: stronger anchor, gentler step
        p['kl'] *= 2; p['lr'] /= 2
    elif rule == 'b':                                      # wins with pipelining hurt: also fine-tune the cell head
        p['cell'] = True
    else:
        raise ValueError('no rule')
    args = f"--epochs {p['epochs']} --lr {p['lr']:g} --kl {p['kl']:g}" + (' --train-cell' if p['cell'] else '')
    return dict(params=p, args=args)


def adapt(path):
    t = _read(path)
    if t is None or not t.strip():
        return dict(verdict='missing')
    m = re.search(r'adaptive vs old: (\d+) paired games.*?adaptive - old ([+-][\d.]+) pp \[([+-][\d.]+), ([+-][\d.]+)\]', t)
    if not m or not t.startswith('VERDICT:') or t.startswith('VERDICT: Failed'):
        return dict(verdict='failed', first=t.splitlines()[0][:200])
    n, d, lo, hi = int(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    return dict(verdict='pass' if (lo > -3.0 and n == 960) else 'nopass', n=n, delta=d, lo=lo, hi=hi)


def _towers(rec):
    p = rec['public']; me = p['observer_side']
    t = [b for b in p['raw_bodies'] if b['card_id'] == -1]
    mine = sum(1 for b in t if b['side'] == me and b['hp'] > 0)
    theirs = sum(1 for b in t if b['side'] != me and b['hp'] > 0)
    return len(t), 3 - mine, 3 - theirs


def one_match(path):
    """-> dict(result, plays=[(tick,name)], pipelined) or None when not a completed full match with the wanted checkpoint."""
    last, plays, ended, piped, sha = None, [], False, 0, None
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('{"event": "decision"'):
            last = line
        elif line.startswith('{"event": "play"'):
            o = json.loads(line); plays.append((o['tick'], o['name']))
        elif line.startswith('{"event": "end"'):
            ended = True; piped = json.loads(line).get('pipelined_plays', 0)
        elif line.startswith('{"event": "start"'):
            sha = json.loads(line).get('ckpt_sha256')
    if not ended or last is None:
        return None
    rec = json.loads(last)
    nt, lost, took = _towers(rec)
    if nt < 2 or rec.get('tick', 0) < 2400:
        return None
    return dict(sha=sha, result='W' if took > lost else 'L' if took < lost else 'D', plays=plays, pipelined=piped)


def count(logdir, since, sha, n=None):
    ms = []
    for f in sorted(glob.glob(os.path.join(logdir, 'live_play_2*.jsonl'))):
        stamp = os.path.basename(f)[len('live_play_'):-len('.jsonl')]
        if stamp < since:
            continue
        try:
            m = one_match(f)
        except (OSError, ValueError, KeyError):
            continue
        if m and m['sha'] == sha:
            ms.append(m)
    ms = ms[:n] if n else ms
    w, l, d = (sum(m['result'] == r for m in ms) for r in 'WLD')
    pairs = tor = plays = 0
    for m in ms:
        pl = sorted(m['plays']); plays += len(pl)
        for a, b in zip(pl, pl[1:]):
            if b[0] - a[0] <= 24:
                pairs += 1; tor += b[1].lower() == 'tornado'
    return dict(n=len(ms), W=w, L=l, D=d, win_rate=(w / (w + l) if w + l else None), plays=plays, fast_pairs=pairs,
                tornado_second=tor, tornado_share=(tor / pairs if pairs else None), pipelined_plays=sum(m['pipelined'] for m in ms))


def running():
    if os.environ.get('FAKE_RUNNING_FILE'):          # dry-run only
        return dict(running=int(_read(os.environ['FAKE_RUNNING_FILE']) or 0))
    import psutil
    n = 0
    for p in psutil.process_iter(['cmdline']):
        cl = ' '.join(p.info.get('cmdline') or [])
        if ('live_play.py' in cl and '--ladder' in cl) or 'live/run_live.sh' in cl:
            n += 1
    return dict(running=n)


def fakelive(logdir, sha, n, tick=3000, tornado_every=4):
    import datetime
    t0 = datetime.datetime.now()
    for i in range(n):
        st = (t0 + datetime.timedelta(seconds=i + 1)).strftime('%Y%m%d_%H%M%S')
        res = ('W', 'L', 'D')[i % 3] if i % 5 == 0 else 'W'
        lost, took = {'W': (0, 1), 'L': (1, 0), 'D': (0, 0)}[res]
        bodies = [dict(card_id=-1, side=0, hp=(1 if k >= lost else 0)) for k in range(3)] + \
                 [dict(card_id=-1, side=1, hp=(1 if k >= took else 0)) for k in range(3)]
        rows = [dict(event='start', ckpt_sha256=sha)]
        rows += [dict(event='play', tick=100 + 10 * k, name=('Tornado' if k % tornado_every == 1 else 'Knight')) for k in range(6)]
        rows += [dict(event='decision', tick=tick, public=dict(observer_side=0, raw_bodies=bodies)), dict(event='end', pipelined_plays=2)]
        with open(os.path.join(logdir, f'live_play_{st}.jsonl'), 'w') as f:
            f.write('\n'.join(json.dumps(r) for r in rows) + '\n')
    return dict(wrote=n)


def summarize(label, c, old=False):
    pct = lambda x: 'n/a' if x is None else f'{100 * x:.1f}%'
    t = (f"[overnight] {label}: {c['n']} completed ladder matches W {c['W']} / L {c['L']} / D {c['D']}, win rate W/(W+L) {pct(c['win_rate'])}."
         + (' Earlier old-model live record: 54.4% (n=379).' if old else '')
         + f" Fast plays: {c['fast_pairs']} quick second-play pairs (<=24 ticks) of {c['plays']} plays, {c['pipelined_plays']} pipelined plays logged;"
         + f" Tornado was the second card in {c['tornado_second']} of them ({pct(c['tornado_share'])}; pros 11.9%, gate 23.8%).")
    return t


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    def w(name, text):
        p = os.path.join(d, name); open(p, 'w').write(text); return p
    cand = 'VERDICT: candidate\nNothing deployed.\n'
    def body(hon, hoff, ton, non, noff):
        return ('VERDICT: not candidate\nx\n\nicebow: not candidate\n'
                f'hard_on: paired n=960\n  fixed-live +0 pp [-1, 1]; non-inferior={hon}; Tornado gate={ton}\n'
                f'hard_off: paired n=960\n  fixed-live +0 pp [-1, 1]; non-inferior={hoff}; Tornado gate=True\n'
                f'old_on: paired n=960\n  fixed-live +0 pp; non-inferior={non}; Tornado gate=True\n'
                f'old_off: paired n=960\n  fixed-live +0 pp; non-inferior={noff}; Tornado gate=True\n')
    assert verdict(w('c', cand))['verdict'] == 'candidate'
    assert verdict(w('a', body(True, True, False, True, True)))['rule'] == 'a'
    assert verdict(w('b', body(False, True, True, True, True)))['rule'] == 'b'
    assert verdict(w('cc', body(True, True, True, True, False)))['rule'] == 'c'
    assert verdict(w('mix', body(False, True, False, True, False)))['rule'] == 'c'      # several failed -> (c) first
    assert verdict(w('mix2', body(False, True, False, True, True)))['rule'] == 'a'      # (a) before (b)
    assert verdict(w('f', 'VERDICT: FAILED (exit 1). See run.log\n'))['verdict'] == 'failed'
    assert verdict(os.path.join(d, 'nope'))['verdict'] == 'missing'
    # a candidate whose first line merely contains the word must not match 'not candidate' as candidate
    assert verdict(w('nc', 'VERDICT: not candidate\n'))['verdict'] == 'not_candidate'
    a1 = nextparams({}, 'a'); assert a1['args'] == '--epochs 10 --lr 0.0002 --kl 100', a1
    a2 = nextparams(a1['params'], 'c'); assert a2['args'] == '--epochs 10 --lr 0.0001 --kl 200', a2
    assert nextparams({}, 'b')['args'].endswith('--train-cell')
    ok = 'VERDICT: Improvement not established. Nothing deployed.\nadaptive vs old: 960 paired games | old 50.0% | adaptive 49.0% | adaptive - old -1.00 pp [-2.10, +0.10]\n'
    assert adapt(w('ap', ok))['verdict'] == 'pass'
    assert adapt(w('an', ok.replace('-2.10', '-3.10')))['verdict'] == 'nopass'
    assert adapt(w('af', 'VERDICT: Failed; no result established.\n'))['verdict'] == 'failed'
    assert fakelive(d, 'abc', 6)['wrote'] == 6
    c = count(d, '19000101_000000', 'abc'); assert c['n'] == 6 and c['W'] + c['L'] + c['D'] == 6, c
    assert c['fast_pairs'] == 6 * 5 and c['tornado_second'] == 6 * 2, c
    assert count(d, '19000101_000000', 'zzz')['n'] == 0
    assert 'win rate W/(W+L)' in summarize('x', c, True) and '54.4%' in summarize('x', c, True)
    print(json.dumps(dict(selftest='PASS')))


if __name__ == '__main__':
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == 'verdict': r = verdict(a[1])
    elif cmd == 'adapt': r = adapt(a[1])
    elif cmd == 'nextparams': r = nextparams(json.loads(a[1]), a[2])
    elif cmd == 'count': r = count(a[1], a[2], a[3], int(a[4]) if len(a) > 4 else None)
    elif cmd == 'running': r = running()
    elif cmd == 'fakelive': r = fakelive(a[1], a[2], int(a[3]))
    elif cmd == 'summarize': print(summarize(a[1], json.loads(a[2]), len(a) > 3)); sys.exit(0)
    elif cmd == 'selftest': r = selftest(); sys.exit(0)
    else: raise SystemExit(__doc__)
    print(json.dumps(r))
