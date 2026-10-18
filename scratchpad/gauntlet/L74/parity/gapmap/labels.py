"""Join every round's failure labels onto the FIN12_stamped failing strict fights (aK < 1) -> joined.tsv + a mass summary.
Sources (newest first; the first label found wins): FIN12-era r7c/labels.txt (hand), r7a class12 (auto, own Skeletons),
r7c + r7d autoclass_fin12.txt (auto first-divergence kind), mine.tsv (this gapmap's own sample); then FIN9-era r6b/r6c/r6d,
FIN7-era r5b/r5d, older r4a. An older-era label whose text says the cause was FIXED, on a fight that still fails, is STALE
(the remaining cause is unknown): class '?'.
Class: H harness / U reader gap / S SIM law / N noise (ceiling <= 0.75 always wins) / ? unlabeled. 'S?' and 'U?' are
provisional (auto first-divergence kind, not hand-checked).
usage: python labels.py ROWS.tsv DIAG_NIGHT_DIR > LABELMASS.txt"""
import re, sys
from collections import defaultdict
from pathlib import Path

KEY = re.compile(r'(\d{8}_\d{6})@(\d+)')


def norm_card(s):
    s = s.strip()
    return s.replace('Skeletons(opp)', 'opp Skeletons').replace('Xbow', 'Xbow')


def cls_of(raw):
    r = raw.strip()
    u = r.upper()
    if u.startswith('N'):
        return 'N'
    if u.startswith('U/NOISE'):
        return 'N'
    if u.startswith('UNRESOLVED'):
        return 'S?'
    if u.startswith('H'):
        return 'H'
    if u.startswith('U'):
        return 'U'
    if u.startswith('S?'):
        return 'S?'
    if u.startswith('S'):
        return 'S'
    if u.startswith('X'):
        return 'S?'
    if u.startswith('P'):
        return 'S?'
    return '?'


AUTO = {'D': 'S?', 'K': 'S?', 'T': 'S?', 'P': 'S?', 'IWCUBE': 'H?', 'U': 'U', 'N': 'N', '?': '?'}
R7A = {'SETUP-STEER': 'U?', 'POS': 'S?', 'UNP': 'S?', 'HP': 'S?', 'TGT': 'S?', 'P': 'N', 'N': 'N'}


def parse(diag):
    D = Path(diag)
    out = []                                         # (stem, t0, cardhint, class, family, text, source)
    rd = lambda p: (D/p).read_text(encoding='utf-8', errors='replace').splitlines() if (D/p).exists() else []
    for ln in rd('r7c/labels.txt'):
        m = KEY.match(ln)
        if not m:
            continue
        f = [x.strip() for x in ln[m.end():].split('|')]
        fam = f[1].split()[1] if len(f[1].split()) > 1 else f[1]
        out.append((m[1], int(m[2]), f[0], cls_of(f[1]), 'r7c:' + fam, ' | '.join(f[1:])[:160], 'r7c'))
    for ln in rd('../gapmap/in/r7a_class12.txt'):
        m = KEY.match(ln)
        if not m:
            continue
        c = ln[m.end():].split()[0]
        out.append((m[1], int(m[2]), 'own Skeletons', R7A.get(c, '?'), 'r7a:' + c, ln[m.end():].strip()[:160], 'r7a'))
    for ln in rd('../gapmap/in/r7b_classes_provisional.txt'):      # r7b/classify.py run as-is (no manual.txt yet)
        f = [x.strip() for x in ln.split(' | ')]
        m = KEY.match(f[1]) if len(f) >= 4 else None
        if not m:
            continue
        c, why = f[2], f[3]
        c = c if c in ('H', 'N') else 'S' if ('UNDER-DAMAGE' in why or 'Mega Knight' in why) else 'S?'
        out.append((m[1], int(m[2]), f[0], c, 'r7b:' + why.split(':')[0].split('[')[0].strip()[:60], why[:160], 'r7b'))
    for ln in rd('../gapmap/mine.tsv'):
        c = ln.split('\t')
        m = KEY.match(c[0]) if c else None
        if not m:
            continue
        out.append((m[1], int(m[2]), c[1], c[2], 'mine:' + c[3], c[4][:160] if len(c) > 4 else '', 'mine'))
    for src in ('r7c/autoclass_fin12.txt', 'r7d/autoclass_fin12.txt'):
        for ln in rd(src):
            m = KEY.match(ln)
            if not m:
                continue
            f = [x.strip() for x in ln[m.end():].split('|')]
            if len(f) < 4:
                continue
            out.append((m[1], int(m[2]), f[1], AUTO.get(f[2], '?'), src[:3] + 'auto:' + f[2], f[3][:160], src[:3] + 'auto'))
    old = []
    for src in ('r6b/labels9.tsv', 'r5b/labels.tsv', 'r4a/labels.tsv'):
        for ln in rd(src):
            c = ln.split('\t')
            m = KEY.match(c[0])
            if not m or len(c) < 3:
                continue
            raw = c[4] if src.startswith('r6b') and len(c) > 4 else c[2]
            txt = '\t'.join(c[2:])
            if src.startswith('r4a'):
                raw = 'H' if txt.startswith('H-') else raw
            old.append((m[1], int(m[2]), c[1], cls_of(raw), src[:3] + ':' + raw[:30], txt[:160], src[:3]))
    for src in ('r6c/labels.txt', 'r6d/labels.txt', 'r5d/labels.txt'):
        for ln in rd(src):
            m = KEY.match(ln)
            if not m:
                continue
            f = [x.strip() for x in ln[m.end():].split('|')]
            if len(f) < 2:
                continue
            old.append((m[1], int(m[2]), f[0], cls_of(f[1]), src[:3] + ':' + f[1][:30], ' | '.join(f[1:])[:160], src[:3]))
    for o in old:
        stale = re.search(r'\bfixed\b|FIXED', o[5]) and not re.search(r'not fixed|unfixed', o[5], re.I)
        out.append(o[:3] + (('?', o[4] + ' [STALE: fixed earlier]') if stale else (o[3], o[4])) + o[5:])
    return out


def match_card(hint, card):
    """does a label's card hint name this fight's anchor card ('own Knight evo' / 'Knight' / 'Witch evo' ...)"""
    h = hint.lower().replace('(opp)', '').strip()
    c = card.lower()
    if h.startswith(('own ', 'opp ')):
        return h == c                                     # a sided label names the exact card + form
    base = h.split('/')[0].split()[0]                     # unsided ('Knight', 'Witch evo', 'Miner/FireSpirits'): base name,
    return c.split(' ')[1] == base and ('evo' not in h or 'evo' in c)   # any form unless the label says evo


def main(rows_path, diag):
    labs = defaultdict(list)
    for x in parse(diag):
        labs[x[0], x[1]].append(x)
    fails = []
    for ln in open(rows_path, encoding='utf-8'):
        c = ln.rstrip('\n').split('\t')
        if c[3] != '1' or c[4] == '' or float(c[4]) >= 1:
            continue
        fails.append(dict(stem=c[0], t0=int(c[1]), card=c[2], aK=float(c[4]), a0=int(c[5]), ceil=float(c[6]) if c[6] else None))
    J = []
    for f in fails:
        cand = [x for x in labs.get((f['stem'], f['t0']), []) if match_card(x[2], f['card'])]
        if f['ceil'] is not None and f['ceil'] <= .75:
            cl, fam, txt, src = 'N', 'ceiling<=0.75', f"ceiling {f['ceil']}", 'ceil'
        elif cand:
            x = cand[0]
            cl, fam, txt, src = x[3], x[4], x[5], x[6]
            if cl == '?' and len(cand) > 1:              # a stale old label: take the next non-stale one if any
                nxt = next((y for y in cand[1:] if y[3] != '?'), None)
                if nxt:
                    cl, fam, txt, src = nxt[3], nxt[4], nxt[5], nxt[6]
        else:
            cl, fam, txt, src = '?', '-', '', '-'
        J.append(dict(f, cls=cl, fam=fam, txt=txt.replace('\t', ' '), src=src))
    with open(Path(rows_path).parent/'joined.tsv', 'w', encoding='utf-8') as fo:
        for j in J:
            fo.write('\t'.join(str(j[k]) for k in ('stem', 't0', 'card', 'aK', 'ceil', 'a0', 'cls', 'fam', 'src', 'txt')) + '\n')
    tot = sum(1-j['aK'] for j in J)
    by = defaultdict(lambda: defaultdict(float))
    rec = defaultdict(lambda: defaultdict(float))
    for j in J:
        by[j['card']][j['cls']] += 1-j['aK']
        rec[j['card']][j['cls']] += max(0., (j['ceil'] if j['ceil'] is not None else 1.) - j['aK'])
    classes = ['H', 'H?', 'U', 'U?', 'S', 'S?', 'N', '?']
    L = [f"failing strict fights {len(J)}, miss mass {tot:.1f}",
         'miss mass by class (all cards): ' + ', '.join(f"{c} {sum(by[k][c] for k in by):.1f}" for c in classes),
         'labeled share of mass: ' + f"{sum(by[k][c] for k in by for c in classes if c != '?')/tot:.3f}", '',
         'card | mass | ' + ' | '.join(classes) + ' | recoverable (ceil - aK) excl. N']
    for k in sorted(by, key=lambda k: -sum(by[k].values())):
        m = sum(by[k].values())
        if m < 2:
            continue
        L.append(f"{k} | {m:.1f} | " + ' | '.join(f"{by[k][c]:.1f}" for c in classes) +
                 f" | {sum(v for c, v in rec[k].items() if c != 'N'):.1f}")
    print('\n'.join(L))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
