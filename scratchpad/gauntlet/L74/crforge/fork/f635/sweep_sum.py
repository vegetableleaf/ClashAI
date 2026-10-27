"""F635 ability sweep summary: python3 sweep_sum.py TABLES_DIR SWEEP.tsv [SWEEP2.tsv ...]
Groups the faulted episodes by message (numbers and object ids replaced by #), and names the culprit: the hero /
champion / evolution forms common to the opponent decks of every pair that hit it. Frequency = how many of the census's
opponent decks (side 1 = the opponent in census_decks.tsv) carry that form; our own deck is side 0."""
import collections, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..', '..'))
try:
    from pipeline.vocab import engine_key  # real card names (vocab.py), when run inside the repo
except ImportError:
    engine_key = lambda n: n  # noqa: E731


def real(form):
    """A form by its real card name: vocab key plus hero / evo / champion."""
    for suffix, kind in (('_hero', 'hero'), ('_EV1', 'evo')):
        if form.endswith(suffix):
            return '%s (%s; %s)' % (engine_key(form[:-len(suffix)]), kind, form)
    return '%s (champion; %s)' % (engine_key(form), form)

champ = set()
for t in ('spells_characters', 'spells_buildings', 'spells_other'):
    for n, r in json.load(open(sys.argv[1] + '/' + t + '.json'))['rows'].items():
        if (r['columns'].get('Rarity') or '') == 'Champion':
            champ.add(n)


def forms(deck, slots):
    out = set()
    for c, s in zip(deck.split(','), map(int, slots.split(','))):
        if s == 2: out.add(c + '_hero')
        elif s == 1: out.add(c + '_EV1')
        if c in champ: out.add(c)
    return out


for path in sys.argv[2:]:
    rows = [l.rstrip('\n').split('\t') for l in open(path)][1:]
    opp = collections.Counter()
    seen_pairs = {}
    for r in rows:
        seen_pairs[r[0]] = r
    for r in seen_pairs.values():
        for f in forms(r[4], r[5]): opp[f] += 1
    groups = collections.defaultdict(list)
    kinds = collections.Counter(r[9] for r in rows)
    for r in rows:
        if r[9] == 'none': continue
        msg = re.sub(r'\b(proj|char|aeo|bld|cmd)_\d+', r'\1_#', r[11])
        msg = re.sub(r'\d+', '#', msg)
        groups[msg].append(r)
    print('== %s: %d episodes over %d pairs; outcome kinds %s' % (path, len(rows), len(seen_pairs), dict(kinds)))
    out = []
    for msg, rs in groups.items():
        pairs = {r[0] for r in rs}
        common = None
        for r in rs:
            f = forms(r[4], r[5])  # the opponent side; our deck (side 0) is the same in every pair
            common = f if common is None else common & f
        culprit = sorted(common or [])
        freq = max([opp[c] for c in culprit] or [0])
        out.append((freq, len(rs), len(pairs), culprit, msg))
    for freq, n, np_, culprit, msg in sorted(out, key=lambda x: (-x[0], -x[1])):
        print('opp decks %3d/%d | episodes %4d | pairs %3d | opponent forms common to all: %s\n    %s' %
              (freq, len(seen_pairs), n, np_, ', '.join(map(real, culprit)) or 'none (our deck, or several)', msg[:400]))
