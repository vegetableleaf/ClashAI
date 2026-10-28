"""SME-FRESH: how often each extractor rule's trigger card (form) is in a deck and played, dev vs fresh, plus non-empty
reader_hidden and ghost rows. python -I trigger_census.py NAME=INPUTS.jsonl ..."""
import json, sys
TRIG = {'hero Valkyrie (BP_VALK)': ('Valkyrie', 2), 'Golden Knight (BP_GK, GK8)': ('GoldenKnight', None),
        'hero Giant (BP_GIANT)': ('Giant', 2), 'Rascals (BP_RASCALS, RASCAL7)': ('Rascals', None),
        'evo Goblin Barrel (MECH_GB)': ('GoblinBarrel', 1), 'Goblin Drill (MECH_DRILL)': ('GoblinDrill', None),
        'hero Balloon (MECH_HB)': ('Balloon', 2), 'Zap (MECH_ZAP, ZAP_ADD/POINT)': ('Zap', None),
        'hero Ice Golem (GOLEM7)': ('IceGolemite', 2), 'opp hero Ice Wizard (IWPEND9, IWGHOST10)': ('IceWizard', 2),
        'hero Mini PEKKA (HIDDEN)': ('MiniPekka', 2), 'Rune Giant (no rule)': ('GiantBuffer', None)}
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1)
    R = [json.loads(l) for l in open(path)]
    print('==', name, len(R), 'records; non-empty reader_hidden:', sum(bool(r.get('reader_hidden')) for r in R),
          '; ghost rows:', sum(bool(p.get('ghost')) for r in R for p in r['plays']))
    for lab, (card, form) in TRIG.items():
        n = 0
        for r in R:
            for s in '01':
                if card == 'IceWizard' and int(s) == r['my_side']:
                    continue
                d = r['sides'][s]
                if any(c == card and (form is None or f == form) for c, f in zip(d['deck'], d['slot_flags'])):
                    n += 1
        print('  %-42s decks %3d' % (lab, n))
