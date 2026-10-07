"""L73 hero dedupe: which production-reader fields separate IceWizardHero / FloatingCube / IceCube among same-side
203000023 objects. Names: Codex's census (details.json, 1,202 records from capture_a/b) and passive_v2_raw.jsonl
(sampler3, 146 named). Census fields are re-decoded from the captured raw bytes with the sampler2 offsets
(live_sampler2.c:347-371: category +0x8, kind +0x30, side +0x78, x +0x7c, y +0x80, card +0xac, behavior +0x11c,
level +0x120, hp/max_hp at *(*(obj+0x18)+0x10)+0x10). Read-only on the main checkout.
Writes named_groups.jsonl (one line per named frame-side group with >=1 203000023 object) and prints stats."""
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

MAIN = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet')
RCI = MAIN / 'L72/improvement_loop/reader_character_identity'
HERE = Path(__file__).resolve().parent
H = 203000023


def i32(b, o=0): return struct.unpack_from('<i', b, o)[0]
def u64(b, o=0): return struct.unpack_from('<Q', b, o)[0]


class Mem:
    def __init__(self, blocks):
        self.b = {a: bytes.fromhex(h) for a, n, h, e in blocks if h is not None}

    def read(self, a, n):
        for p, b in self.b.items():
            if p <= a and a + n <= p + len(b):
                return b[a - p:a - p + n]
        return None


def obj_fields(m, a):
    raw = m.read(a, 0x128)
    if raw is None:
        return None
    e = dict(address=hex(a), category=i32(raw, 8), kind=i32(raw, 0x30), side=i32(raw, 0x78), x=i32(raw, 0x7c),
             y=i32(raw, 0x80), card_id=i32(raw, 0xac), behavior_state_raw=i32(raw, 0x11c), level=i32(raw, 0x120),
             hp=-1, max_hp=-1)
    comp = u64(raw, 0x18)
    hp = comp and m.read(comp + 0x10, 8)
    hp = hp and u64(hp)
    pair = hp and m.read(hp + 0x10, 8)
    if pair:
        e['hp'], e['max_hp'] = i32(pair), i32(pair, 4)
    return e


def census_groups():
    d = json.load(open(RCI / 'details.json'))
    want = defaultdict(list)
    for x in d:
        want[(x['capture'], x['seq'])].append(x)
    for cap in ('capture_a.jsonl', 'capture_b.jsonl'):
        for line in open(MAIN / 'L70/reader' / cap):
            f = json.loads(line)
            rows = want.get((cap, f.get('seq')))
            if not rows:
                continue
            m = Mem(f['blocks'])
            groups = defaultdict(list)
            for x in sorted(rows, key=lambda r: r['batch_index']):
                e = obj_fields(m, int(x['address'], 16))
                assert e and e['card_id'] == H and e['side'] == x['side'] and e['category'] == x['category'], x
                e.update(native_name=x['native_name'], attached_owner=x['attached_owner'], order=x['batch_index'])
                groups[x['side']].append(e)
            for side, g in groups.items():
                yield f'{cap}:{f["seq"]}', rows[0]['tick'], side, g


def passive_groups():
    for line in open(RCI / 'passive_v2_raw.jsonl'):
        f = json.loads(line)
        groups = defaultdict(list)
        for i, e in enumerate(f['entities']):
            if e.get('card_id') == H:
                groups[e['side']].append(dict(e, order=i))
        for side, g in groups.items():
            yield f'passive_v2:{f["sequence"]}', f['game_tick'], side, g


def main():
    st = Counter()
    with open(HERE / 'named_groups.jsonl', 'w') as out:
        for src, tick, side, g in list(census_groups()) + list(passive_groups()):
            out.write(json.dumps(dict(src=src, tick=tick, side=side, objs=g)) + '\n')
            pre = src.split(':')[0]
            names = [e.get('native_name') for e in g]
            st[f'{pre} groups'] += 1
            st[f'{pre} groups n_hero={names.count("IceWizardHero")} n_obj={len(g)}'] += 1
            heroes = {e['address']: e for e in g if e.get('native_name') == 'IceWizardHero'}
            for e in g:
                n = e.get('native_name') or 'UNNAMED'
                st[f'{n} kind={e["kind"]}'] += 1
                st[f'{n} hp==max_hp:{e["hp"] == e["max_hp"]} hp_read:{e["hp"] >= 0}'] += 1
                if n == 'IceWizardHeroFloatingCube':
                    p = heroes.get(e.get('attached_owner'))
                    st[f'cube owner hero in group:{p is not None}'] += 1
                    if p:
                        st[f'cube colocated with owner:{(p["x"], p["y"]) == (e["x"], e["y"])}'] += 1
                        st[f'cube category - owner category = {e["category"] - p["category"]}'] += 1
                        st[f'cube listed after owner:{e["order"] > p["order"]}'] += 1
                        st[f'cube hp>=owner hp:{e["hp"] >= p["hp"]}'] += 1
                if n == 'IceWizardHero_IceCube':
                    near = [h for h in heroes.values() if abs(h['x'] - e['x']) <= 500 and abs(h['y'] - e['y']) <= 500]
                    st[f'icecube within 500 of a hero:{bool(near)}'] += 1
                    st[f'icecube hp={e["hp"]}/{e["max_hp"]} kind={e["kind"]} beh={e["behavior_state_raw"]}'] += 1
    for k in sorted(st):
        print(f'{k}: {st[k]}')


if __name__ == '__main__':
    main()
