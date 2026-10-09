"""The L74 identity census table: target body groups (live census.json [+ census_ext.json] + native_scan.json).
Each row: reader id / catalog name / form, HP values seen live, what the body is (evidence: pipeline/body_identity.py EXT_* comments, wiki/), the class
the model receives today (and with --identity-ext on), bodies / decision states / matches, W-L in those matches, and
how the TRAINING corpora carry the same body (native_scan, level 11).  python table.py -> table.out
"""
import collections, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
# (label, card_id, name, form, live HP set or None = all, native target, native HP (level 11), what it is)
GROUPS = [
    ('new: Evo Elite Barbarians', 13000043, None, None, None, None, None, 'evolved Elite Barbarians (HP = AngryBarbarians L14-16)'),
    ('new: Hero Electro Wizard', 203000042, None, None, None, None, None, 'Hero Electro Wizard (HP = ElectroWizard L11/14/16)'),
    ('new: Minion Giant', 26000107, None, None, None, None, None, 'Minion Giant (HP = RoyaleSim MinionGiant L11/13)'),
    ('new: Evo Electro Giant', 13000075, None, None, None, None, None, 'evolved Electro Giant (HP = ElectroGiant L11/16)'),
    ('Hero Balloon ability', 203000006, 'Balloon', 2, {627, 688, 756, 832}, 'Balloon@hero', 473, 'Skeletrooper (wiki 473@L11)'),
    ('Hero Dark Prince ability', 203000027, 'DarkPrince', 2, {1796, 1971}, 'DarkPrince@hero', 1356, 'Rhino mount (wiki 1356@L11)'),
    ('Hero Musketeer ability', 203000014, 'Musketeer', 2, {1536, 1854, 2034, 2232, 2454}, 'Musketeer@hero', 1536, 'Trusty Turret (wiki 1536@L11)'),
    ('Hero Tombstone ability', 203000088, 'Tombstone', 2, {4224, 5593}, 'Tombstone@hero', 4224, 'Queen (wiki 4224@L11)'),
    ('Hero Goblins ability', 203000002, 'Goblins', 2, {3390, 3720, 4090}, 'Goblins@hero', 2560, 'Banner (2560@L11 native)'),
    ('Hero Magic Archer ability', 203000062, 'EliteArcher', 2, {271, 394, 433}, 'EliteArcher@hero', 271, 'decoy (wiki 271@L11)'),
    ('Little Prince ability', 26000093, 'LittlePrince', 0, {1600, 1931, 2118, 2325, 2556}, 'LittlePrince', 1600, 'Guardienne (catalog ChampionGuard)'),
    ('Evo Mortar spawn', 13000098, 'Mortar', 1, {267, 293, 323}, 'Mortar@evolution', 202, 'Goblin (catalog Mortar_EV1 -> Goblin)'),
    ('Evo Royal Ghost spawn', 13000050, 'Ghost', 1, {81, 108, 119, 130}, 'Ghost@evolution', 81, 'Souldier (catalog Ghost_EV1_Summon, wiki 81/81)'),
    ('Evo Skeleton Army spawn', 13000012, 'SkeletonArmy', 1, {2, 3, 4}, 'SkeletonArmy@evolution', 2, 'spectral skeleton (catalog SkeletonArmy_EV1_Spectral)'),
    ('Evo Lumberjack spawn', 13000035, 'RageBarbarian', 1, {2, 3, 4}, 'RageBarbarian@evolution', 2, 'ghost (catalog RageBarbarianEvoGhost)'),
    ('Evo Wall Breakers spawn', 13000058, 'Wallbreakers', 1, {216, 238}, 'Wallbreakers@evolution', 163, 'Wallbreaker_mini (catalog)'),
    ('Evo Battle Ram spawn', 13000036, 'BattleRam', 1, {716, 949, 1041, 1145}, 'BattleRam@evolution', 716, 'Barbarian (catalog Barbarian_EV1)'),
    ('Goblin Cage spawn', 27000012, 'GoblinCage', 0, None, 'GoblinCage', 1080, 'Goblin Brawler (child_no_class)'),
    ('Evo Goblin Cage spawn', 13000107, 'GoblinCage', 1, None, 'GoblinCage@evolution', 1080, 'Goblin Brawler (child_no_class)'),
    ('Phoenix spawn', 26000087, 'Phoenix', 0, None, 'Phoenix', 317, 'Phoenix egg (child_no_class)'),
]


def load(fn):
    p = os.path.join(HERE, fn)
    return json.load(open(p))['rows'] if os.path.exists(p) else None


def main():
    live, ext = load('census.json'), load('census_ext.json')
    nat = json.load(open(os.path.join(HERE, 'native_scan.json')))
    res = {}
    import sys
    sys.path.insert(0, 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review')
    for l in open('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/runover/matches.jsonl'):
        m = json.loads(l); res[m['file']] = m['result']
    try:
        import review as V
        for f, (r, _) in V.ladder_results().items():
            res.setdefault(f, r)
    except Exception:
        pass
    allf = {f for r in live for f in r['files']}
    known = [res[f] for f in allf if f in res]
    base = collections.Counter(known)
    print(f"all census logs with bodies: {len(allf)}; result known {len(known)}: {dict(base)} "
          f"(loss rate {base['LOSS'] / max(1, base['WIN'] + base['LOSS']):.1%} of W+L)\n")
    hdr = ('group', 'reader id', 'HP live', 'is', 'model today', 'ext on', 'bodies', 'states', 'matches', 'W-L-?',
           'loss%', 'training (native sample, L11)')
    print(' | '.join(hdr))
    for label, cid, name, form, hps, ntarget, nhp, what in GROUPS:
        rows = [r for r in live if r['card_id'] == cid and (hps is None or r['max_hp'] in hps)]
        if name is None:
            pass
        if hps is None and label.endswith('spawn') and cid in (27000012, 13000107, 26000087):
            rows = [r for r in rows if r['reason'] == 'child_no_class']
        if not rows:
            print(f'{label} | {cid} | none in live logs'); continue
        files = sorted({f for r in rows for f in r['files']})
        rc = collections.Counter(res.get(f, '?') for f in files)
        cls = sorted({f"{r['cls']}({r['reason']})" for r in rows})
        ecls = '-'
        if ext is not None:
            keys = {(r['card_id'], r['max_hp']) for r in rows}
            ecls = ', '.join(sorted({f"{r['cls']}({r['reason']})" for r in ext if (r['card_id'], r['max_hp']) in keys}))
        nrows = [r for r in nat['rows'] if r['target'] == ntarget and r['max_hp'] == nhp
                 and r['card_id'] == (cid if cid != 26000087 or True else cid)] if ntarget else []
        ntxt = ('; '.join(f"{r['cls']} f{r['cls_form']} {r['bodies']} bodies/{r['replays']} replays" for r in nrows)
                if ntarget else 'absent (card/form not in the native catalog)')
        wl = rc['WIN'] + rc['LOSS']
        print(' | '.join(map(str, (label, cid, sorted({r['max_hp'] for r in rows}), what, ', '.join(cls), ecls,
                                    sum(r['bodies'] for r in rows), sum(r['states'] for r in rows) + sum(r['fstates'] for r in rows),
                                    len(files), f"{rc['WIN']}-{rc['LOSS']}-{len(files) - wl}",
                                    f"{rc['LOSS'] / wl:.0%}" if wl else 'n/a', ntxt))))


if __name__ == '__main__':
    main()
