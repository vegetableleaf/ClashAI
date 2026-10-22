"""PATCH1019 table (W23): cards-160402017-20261019.json = the fork's 10-06 table with exactly the field deltas the fork's own
extractor yields between content 16.402.21 and 16.402.22 (the 2026-10-19 update), every other field byte-identical.

  python make_table.py BASE_1006.json A_21.json B_22.json DECODED_22_CSV_LOGIC OUT.json DELTAS.txt
BASE_1006 = data/derived/cards-160402017-20261006.json (committed); A_21 / B_22 = tools/extract_cards.py --vintage
160402017-20261006 / 160402017-20261019 run on one base (PATCH1019.md section 4); DECODED_22_CSV_LOGIC = the decoded
update folder (data/raw/cr-160402017-20261019/csv_logic), whose file hashes replace the base's for the files it changed.
A delta is applied only where BASE holds A's value (else the build stops): the table changes by the update, nothing else."""
import hashlib
import json
import sys
from pathlib import Path

ABSENT = object()
SKIP_TOP = {'version', 'vintage_warning', 'provenance'}
CHANGED_FILES = ('characters/blowdartgoblin.toml', 'characters/cannon_cart.toml', 'characters/dark_magic.toml',
                 'characters/dartbarrell.toml', 'characters/electrodragon.toml', 'characters/giant_buffer_v2.toml',
                 'characters/hero_form/electro_wizard_hero.toml', 'characters/minion_giant.toml',
                 'characters/skeleton_balloon.toml', 'characters/skeleton_balloon_ev1.toml', 'globals.csv',
                 'spells_characters.toml', 'spells_evolved.toml')


def named(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) and 'name' in x for x in v)


def merge(a, b, c, path, log):
    """c with a -> b applied wherever a and b differ; c must equal a there."""
    if a == b:
        return c
    if isinstance(a, dict) and isinstance(b, dict) and isinstance(c, dict):
        out = dict(c)
        for k in list(a) + [k for k in b if k not in a]:
            if path == '' and k in SKIP_TOP:
                continue
            v = merge(a.get(k, ABSENT), b.get(k, ABSENT), c.get(k, ABSENT), f'{path}.{k}', log)
            if v is ABSENT:
                out.pop(k, None)
            else:
                out[k] = v
        return out
    if named(a) and named(b) and named(c):
        ia, ib, ic = ({x['name']: x for x in v} for v in (a, b, c))
        if list(ia) != list(ic) or set(ia) != set(ib):
            raise SystemExit(f'{path}: rows differ in name or order')
        return [merge(ia[n], ib[n], ic[n], f'{path}[{n}]', log) for n in ic]
    if c != a:
        raise SystemExit(f'{path}: base holds {json.dumps(c)[:120]}, not the 16.402.21 value {json.dumps(a)[:120]}')
    log.append(f'{path} | {json.dumps(a) if a is not ABSENT else "<absent>"} -> {json.dumps(b) if b is not ABSENT else "<absent>"}')
    return b


def main():
    base_p, a_p, b_p, dec, out_p, deltas_p = sys.argv[1:7]
    base, a, b = (json.loads(Path(p).read_text(encoding='utf-8')) for p in (base_p, a_p, b_p))
    log = []
    out = merge(a, b, base, '', log)
    out['version'] = 'cards-160402017-20261019.1'
    out['vintage_warning'] = b['vintage_warning']
    prov = dict(base['provenance'])
    for k in ('source', 'vintage', 'roster_dating', 'vintage_key'):
        prov[k] = b['provenance'][k]
    files = dict(prov['files'])
    for rel in CHANGED_FILES:
        if rel in files:
            files[rel] = {'sha256': hashlib.sha256((Path(dec) / rel).read_bytes()).hexdigest()}
    prov['files'] = files
    prov['derivation'] = (
        'W23 PATCH1019 (scratchpad/gauntlet/L74/patch1019/make_table.py): cards-160402017-20261006.1 with exactly the '
        f'{len(log)} field deltas tools/extract_cards.py yields between content 16.402.21 and 16.402.22 on one base; '
        'every other field is the 10-06 table\'s. The 16.402.21-only changes (Evo Electro Giant pulse filter '
        'CommonAreaDamageFilterNoClones; the Hero Electro Wizard\'s Forbid_Movement links and refund window) are NOT in '
        'it. files: the 10-06 inputs, with the decoded 16.402.22 hashes for the 13 files the update changed.')
    order = list(base)                 # keep the 10-06 key order
    out = {k: out[k] for k in order}
    Path(out_p).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    Path(deltas_p).write_text('\n'.join(log) + '\n', encoding='utf-8')
    print(len(log), 'deltas ->', out_p)


if __name__ == '__main__':
    main()
