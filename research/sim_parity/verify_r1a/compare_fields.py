# -*- coding: utf-8 -*-
"""Compare CycleCost + ReleaseDate parsed from archived subpage wikitext
against the claimed r1a table (claimed values embedded here from the task)."""
import re, json, datetime

WEB = 'C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
claimed = {
 'Barbarians': ('2023-06-19', 1), 'Royal Giant': ('2023-06-19', 1),
 'Firecracker': ('2023-06-19', 2), 'Skeletons': ('2023-06-19', 2),
 'Mortar': ('2023-07-03', 2), 'Knight': ('2023-08-07', 2),
 'Royal Recruits': ('2023-09-04', 1), 'Bats': ('2023-10-02', 2),
 'Archers': ('2023-11-06', 2), 'Ice Spirit': ('2023-12-04', 2),
 'Valkyrie': ('2024-01-01', 2), 'Bomber': ('2024-02-05', 2),
 'Wall Breakers': ('2024-02-14', 2), 'Tesla': ('2024-03-04', 2),
 'Zap': ('2024-03-11', 2), 'Battle Ram': ('2024-04-01', 2),
 'Wizard': ('2024-05-06', 1), 'Goblin Barrel': ('2024-06-03', 2),
 'Goblin Giant': ('2024-07-01', 1), 'Goblin Drill': ('2024-07-15', 2),
 'Goblin Cage': ('2024-08-05', 2), 'P.E.K.K.A.': ('2024-09-02', 1),
 'Mega Knight': ('2024-09-14', 1), 'Electro Dragon': ('2024-10-07', 1),
 'Musketeer': ('2024-11-04', 2), 'Cannon': ('2024-11-15', 2),
 'Giant Snowball': ('2024-12-02', 2), 'Dart Goblin': ('2025-01-06', 2),
 'Lumberjack': ('2025-02-03', 2), 'Hunter': ('2025-03-03', 2),
 'Executioner': ('2025-04-07', 1), 'Witch': ('2025-05-05', 1),
 'Inferno Dragon': ('2025-06-02', 2), 'Skeleton Barrel': ('2025-07-07', 2),
 'Furnace': ('2025-08-04', 2), 'Baby Dragon': ('2025-09-01', 2),
 'Skeleton Army': ('2025-10-06', 2), 'Royal Ghost': ('2025-10-17', 2),
 'Royal Hogs': ('2025-11-03', 2), 'Minion Horde': ('2026-04-06', 1),
 'Princess': ('2026-06-01', 2), 'Elite Barbarians': ('2026-08-03', 1),
}

MONTHS = {m: i+1 for i, m in enumerate(['January','February','March','April','May',
          'June','July','August','September','October','November','December'])}

def parse_date(s):
    s = s.strip()
    m = re.match(r'(\d{1,2})\s+([A-Za-z]+)\s*,?\s*(\d{4})', s)      # 7 August 2023
    if m: return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    m = re.match(r'([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})', s)        # April 6,2026
    if m: return datetime.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    m = re.match(r'([A-Za-z]+)\s+(\d{4})$', s)                        # June 2026
    if m: return ('month-only', m.group(1), m.group(2))
    return ('unparsed', s)

mismatch, ok = [], 0
for card, (cd, cc) in sorted(claimed.items()):
    fn = WEB + card.replace('/', '_').replace(' ', '_') + '_Evolution.wikitext'
    wt = open(fn, encoding='utf-8').read()
    mcc = re.search(r'CycleCost\s*=\s*(\d+)', wt)
    mrd = re.search(r'ReleaseDate\s*=\s*([^|}\n]+)', wt)
    wiki_cc = int(mcc.group(1)) if mcc else None
    wiki_rd = parse_date(mrd.group(1)) if mrd else None
    problems = []
    if wiki_cc != cc:
        problems.append(f'cycles: wiki={wiki_cc} claimed={cc}')
    if isinstance(wiki_rd, datetime.date):
        if wiki_rd.isoformat() != cd:
            problems.append(f'date: wiki={wiki_rd.isoformat()} claimed={cd}')
    else:
        problems.append(f'date not directly comparable: wiki_raw={wiki_rd} claimed={cd}')
    if problems:
        mismatch.append((card, problems))
    else:
        ok += 1

print(f'{ok}/42 subpage infoboxes match claimed (release_date, evo_cycles) exactly')
for card, probs in mismatch:
    print('CHECK', card, '->', '; '.join(probs))
