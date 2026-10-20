"""W9 identity inventory: every card / evolution / hero form of the device tables (10-12) x
  catalog  -- the live catalog names its id (before = pre-W9 file, after = extended file)
  vocab    -- the model's unit vocab gives it its own class (before = commit 17cb3f3's vocab, after = working tree);
              a form is exact as (base class, form flag), the observation's form column
  gen      -- the live checkpoint's GenModel card_vocab has its slug (opponent past / cycle card identity)
  sim      -- the SIM runtime plays it in that form (sim_probe_0136.json) with table stats equal to the device's
              (W1 static_check: parity/output/metrics/static.json, royalesim 0.1.36 table)
  reader   -- live reader id -> catalog name/form -> vocab class is its own class and form
  live     -- distinct reader bodies / logs with that id (raw_id_census.json, 4,534 live logs)

  python inventory.py   -> inventory.json + INVENTORY.md next to this file
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from pipeline import vocab  # noqa: E402

DEVICE = HERE.parent / 'apktables/out/device_builds/20261012T221627332682Z-50188/cards.json'
CAT = ROOT / 'research/ext/cr-native-sandbox/native_core/data'
STATIC = HERE.parent / 'parity/output/metrics/static.json'
CKPT = ROOT / 'icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt'
OLD_VOCAB_REV = '17cb3f3'
FORM = ('base', 'evo', 'hero')


def old_vocab():
    src = subprocess.run(['git', '-C', str(ROOT), 'show', f'{OLD_VOCAB_REV}:pipeline/vocab.py'], capture_output=True,
                         text=True, check=True).stdout
    p = Path(tempfile.mkdtemp()) / 'vocab_old.py'
    p.write_text(src, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('vocab_old', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def forms_table(cards):
    t = {}
    for c in cards:
        for f, k in enumerate(('card_id', 'evolution_form_id', 'hero_form_id')):
            if c.get(k) is not None:
                t[int(c[k])] = (c['display_name'], f)
    t.setdefault(203000023, ('IceWizard', 2))           # pipeline/reader_identity_aliases (both before and after)
    return t


def own_class(v, name, ladder_names):
    """The vocab class of an engine name, and whether it is the card's OWN (no other ladder card shares it)."""
    cid = v.engine_unit_id(name)
    if cid is None:
        return None, False
    shared = [n for n in ladder_names if n != name and v.engine_unit_id(n) == cid]
    return v.UNIT_VOCAB[cid], not shared


def main():
    import torch
    dev = json.loads(DEVICE.read_text(encoding='utf-8'))
    sys.path.insert(0, str(HERE))
    from gen_catalog import ids as table_ids
    ids = {n: i for t in table_ids(DEVICE.parent / 'tables/csv_logic').values() for n, (i, _) in t.items()}
    before = json.loads((CAT / 'live_card_catalog.pre_w9_20261020.json').read_text(encoding='utf-8'))['cards']
    after = json.loads((CAT / 'live_card_catalog.json').read_text(encoding='utf-8'))['cards']
    fb, fa = forms_table(before), forms_table(after)
    std = {c['internal_name']: bool(c['standard_1v1']) for c in after}
    ladder = [c['name'] for c in dev['cards'] if std.get(c['name'])]
    vo = old_vocab()
    probe = json.loads((HERE / 'sim_probe_0136.json').read_text(encoding='utf-8'))['cards']
    static = {r['card']: r for r in json.loads(STATIC.read_text(encoding='utf-8'))['device_vs_sim']}
    census = json.loads((HERE / 'raw_id_census.json').read_text(encoding='utf-8'))['ids']
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    gen_vocab = set(ck.get('card_vocab') or [])
    from pipeline.dataset_gen import card_key
    rows = []
    for sec, f in (('cards', 0), ('evolutions', 1), ('hero_forms', 2)):
        for c in dev[sec]:
            base = c['name'] if f == 0 else c['form_of']
            cid = ids[c['name']]
            r = dict(id=cid, name=c['name'], base=base, display=c['display_name'], form=FORM[f], type=c['kind'],
                     elixir=c['elixir'], rarity=c['rarity'], ladder=std.get(base, False))
            live = census.get(str(cid)) or {}
            r.update(live_bodies=live.get('bodies', 0), live_logs=live.get('logs', 0))
            r['catalog_before'] = fb.get(cid) == (base, f)
            r['catalog_after'] = fa.get(cid) == (base, f)
            for tag, v in (('before', vo), ('after', vocab)):
                cls, own = own_class(v, base, ladder)
                r[f'vocab_{tag}'] = cls
                r[f'vocab_own_{tag}'] = own
                # reader: id -> catalog name/form -> class; exact = own class AND the id's form
                name, form = (fb if tag == 'before' else fa).get(cid, (None, 0))
                rc = v.engine_unit_id(name) if name else None
                r[f'reader_{tag}'] = None if rc is None else f'{v.UNIT_VOCAB[rc]}/{form}'
                r[f'reader_exact_{tag}'] = rc is not None and own and form == f
            r['gen_card_vocab'] = card_key(base) in gen_vocab
            pr = (probe.get(base) or {}).get(str(f))
            r['sim'] = None if pr is None else ('OK' if 'refused' not in pr and pr['reason'] == 'OK' else
                                                pr.get('refused') or pr['reason'])
            st = static.get(c['name'])
            r['sim_table'] = None if st is None else st['status']
            r['sim_table_diffs'] = [] if st is None else [f"{d['field']}: {d['sim']} -> {d['device']}" for d in st['diffs']
                                                          if not d.get('override')]
            m = (c.get('level_scaling') or {}).get('multiplier_percent_by_level') or []
            want = c['hitpoints'] * m[10] // 100 if isinstance(c.get('hitpoints'), int) and len(m) > 10 else None
            got = (pr or {}).get('new') or []
            r['sim_hp_l11'] = None if not got or want is None else (got[0]['max_hp'], want)
            rows.append(r)
    out = HERE / 'inventory.json'
    out.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    write_md(rows)
    print('rows', len(rows), '->', out)


def gaps(r):
    g = []
    if not r['catalog_after']:
        g.append('catalog')
    if r['vocab_after'] is None or not r['vocab_own_after']:
        g.append('vocab')
    if not r['reader_exact_after']:
        g.append('reader')
    if r['form'] == 'base' and r['ladder'] and not r['gen_card_vocab']:
        g.append('gen card_vocab')
    if r['sim'] != 'OK' and r['name'] != 'Mirror':
        g.append('sim load')
    if r['sim_table'] not in ('equal', 'override_resolved'):
        g.append('sim table')
    if r['sim_hp_l11'] and r['sim_hp_l11'][0] != r['sim_hp_l11'][1]:
        g.append('sim hp')
    return g


def write_md(rows):
    yn = lambda b: 'yes' if b else '**no**'
    lines = ['# Identity inventory (generated by inventory.py; W9 2026-10-20)', '',
             'One row per card / evolution / hero form in the 10-12 device tables (145 + 43 + 18). before = pre-W9 '
             '(catalog backup live_card_catalog.pre_w9_20261020.json, vocab of commit 17cb3f3), after = this change. '
             'live = reader bodies (logs) with this id in 4,534 live logs. sim = royalesim 0.1.36 play probe; table = W1 '
             'static_check device_vs_sim. Gaps are AFTER this change.', '',
             '| id | card | form | type | elixir | ladder | live bodies (logs) | catalog b/a | vocab class b -> a | reader b -> a | '
             'gen card_vocab | sim plays | sim table | gaps |', '|' + '---|' * 14]
    for r in sorted(rows, key=lambda r: (-r['live_bodies'], r['id'])):
        lines.append(f"| {r['id']} | {r['name']} | {r['form']} | {r['type']} | {r['elixir']} | {yn(r['ladder'])} | "
                     f"{r['live_bodies']} ({r['live_logs']}) | {yn(r['catalog_before'])} / {yn(r['catalog_after'])} | "
                     f"{r['vocab_before']}{'' if r['vocab_own_before'] else ' (shared)'} -> {r['vocab_after']}"
                     f"{'' if r['vocab_own_after'] else ' (shared)'} | {r['reader_before']}{'' if r['reader_exact_before'] else ' X'} -> "
                     f"{r['reader_after']}{'' if r['reader_exact_after'] else ' X'} | "
                     f"{yn(r['gen_card_vocab']) if r['form'] == 'base' else ''} | {r['sim']} | {r['sim_table']} | "
                     f"{', '.join(gaps(r))} |")
    n = len(rows)
    cnt = defaultdict(int)
    for r in rows:
        for g in gaps(r):
            cnt[g] += 1
    lines[3:3] = [f'Rows {n}. Gap counts after this change: {dict(cnt)}. Before: catalog missing '
                  f"{sum(not r['catalog_before'] for r in rows)}, reader inexact {sum(not r['reader_exact_before'] for r in rows)}, "
                  f"vocab shared/missing {sum(r['vocab_before'] is None or not r['vocab_own_before'] for r in rows)}.", '']
    (HERE / 'INVENTORY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
