"""Walk every RECON/gate run dir under /workspace/smeR*/runs, one row per (run, match):
exact/torn/div counts, first_div, and the Hero IceWizard ability presses in the plan.
Output: JSON lines on stdout. Read-only."""
import glob, json, os

rows = []
for root in sorted(glob.glob('/workspace/smeR*/runs')):
    tree = root.split('/')[2]
    for pf in glob.glob(root + '/*/*/recon_plan.json') + glob.glob(root + '/*/*/plan.json'):
        d = os.path.dirname(pf)
        rf = os.path.join(d, 'recon_result.json')
        if not os.path.exists(rf):
            rf = os.path.join(d, 'result.json')
        if not os.path.exists(rf):
            continue
        try:
            p = json.load(open(pf))
            r = json.load(open(rf))
        except Exception:
            continue
        cmds = p.get('cmds', [])
        slots = p.get('slots')
        decks = p.get('decks')
        presses = []
        for i, c in enumerate(cmds):
            if c.get('kind') != 'ability':
                continue
            u = c.get('unit') or ''
            lu = c.get('late_unit')
            card = None
            if u.startswith('cmd') and '_' in u:
                try:
                    k = int(u[3:].split('_')[0])
                    card = cmds[k].get('card')
                    pside = cmds[k].get('side')
                except Exception:
                    pside = None
            else:
                pside = c.get('side')
            side = c.get('side')
            hero = None
            if card and decks and slots:
                try:
                    di = decks[side].index(card)
                    hero = slots[side][di]
                except Exception:
                    hero = None
            presses.append({'i': i, 'side': side, 'run': c.get('run'), 'card': card, 'late_unit': lu,
                            'unit': u, 'slotflag': hero, 'src': (c.get('_src') or {}).get('source')})
        counts = r.get('counts', {})
        rows.append({'tree': tree, 'run': d.split('/')[-2], 'match': os.path.basename(d),
                     'frames': r.get('frames'), 'counts': counts, 'first_div': r.get('first_div'),
                     'flags': r.get('flags'), 'ncmds': len(cmds),
                     'presses': [x for x in presses], 'path': d})
for r in rows:
    print(json.dumps(r))
