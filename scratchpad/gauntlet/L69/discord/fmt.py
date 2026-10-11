"""Owner 2026-10-10: make the pod stage reports readable. post.py runs every message through readable(); messages that are
not stage reports ("[weekend <stage> done] ..." or anything with a VERDICT line) pass through unchanged."""
import re

NAMES = {'S2': 'New live model vs old (960 sim games)', 'S3': 'Prevent vs delay test', 'S4': 'Tower Rocket split by elixir',
         'S5': 'Defence training E5', 'S6': 'Own-cycle training', 'S7': 'New simulator version check',
         'S8': 'Log Bait baseline', 'S9': 'Drill scoring (small)', 'S9XL': 'Drill scoring, large (D2 D3 D10)',
         'S10': 'Drill training', 'S10XL': 'Drill training on D2 + D3', 'S9XL2': "Drill scoring, all drills + 'when pros would'",
         'S10XL2': 'Drill training on every confirmed drill', 'S11_bait': 'Log Bait training (base cards)',
         'ADAPT': 'Adaptive-opponent training',
         'BAIT_CMP': 'Log Bait specialist vs generalist',
         'MEMP1': 'Match memory: pro dataset with histories', 'MEMP2': 'Match memory: memory-only pretraining',
         'MEMP3': 'Match memory: adaptive league training', 'MEMP4': 'Match memory: 960-game test vs the old live model'}
NEXT = {'S10XL': 'Next: the all-drills scoring run starts automatically.',
        'S9XL2': 'Next: training on the confirmed drills starts automatically.',
        'S10XL2': "If it says 'candidate', reply to approve a deploy -- nothing deploys on its own.",
        'S11_bait': 'Next: pod 2 moves on to its share of the drills (D5, D6).'}
WORDS = [(r'win DO - HOLD', 'doing it vs the alternative'), (r'DO - own', 'doing it vs the model\'s own choice'),
         (r'HOLD - own', 'holding back vs the model\'s own choice'), (r'win B - A', 'forced move vs the model\'s choice'),
         (r'\bpp\b', 'points'), (r'tower diff', 'tower HP lead'), (r'\(n \d+, matches \d+\)', ''),
         (r'\(win CI half-width [^)]*\)', '')]


def _plain(line: str) -> str:
    line = re.sub(r'([+-]?\d+\.\d{3,})', lambda m: f'{float(m.group(1)) * (100 if abs(float(m.group(1))) < 1 else 1):+.1f}', line) \
        if ('DO - ' in line or 'B - A' in line) and 'pp' not in line else line   # win fractions -> points
    line = re.sub(r'\[([+-]?[\d.]+), ([+-]?[\d.]+)\]', r'(range \1 to \2)', line)
    for a, b in WORDS:
        line = re.sub(a, b, line)
    return re.sub(r'\s{2,}', ' ', line).strip()


def readable(text: str) -> str:
    m = re.match(r'\[weekend (\S+) done\]\s*(.*)', text, re.S)
    if 'weekend queue done' in text and not m:
        return ('First half of the weekend chain finished; its results are copied to the laptop.\n'
                'Not everything is done: the all-drills run continues on the pods and reports here as each part finishes.')
    if not m and 'VERDICT' not in text:
        return text
    stage, body = (m.group(1), m.group(2)) if m else ('', text)
    lines = [l for l in body.splitlines() if l.strip()]
    verdicts = [_plain(l.split('VERDICT:', 1)[1]) for l in lines if 'VERDICT:' in l]
    key = [_plain(l) for l in lines if 'VERDICT:' not in l and re.search(r'label|vs |win|%|points|pp|Improvement|Memory benefit', l)]
    seed = re.match(r'seed ([AB])\b', lines[0]) if lines else None      # relay puts 'seed A/B' on the first body line
    out = [f"**{NAMES.get(stage, stage or 'Pod stage')}{' (seed ' + seed.group(1) + ')' if seed else ''} -- finished**"]
    if verdicts:
        out.append('**Verdict:** ' + ' / '.join(dict.fromkeys(verdicts)))
    out += ['- ' + k[:230] for k in key[:10]]
    if stage in NEXT:
        out.append(NEXT[stage])
    out.append('(Full numbers: the stage SUMMARY.txt in the results copy on the laptop.)')
    return '\n'.join(out)[:1900]


if __name__ == '__main__':
    s = readable('[weekend S10XL done] train: SAVED x\nwk_s10xl_lv vs live_new_lv: 960 paired games | live 70.2% | new 66.9% | '
                 'new - live -3.33 pp [-7.02, +0.35]\nVERDICT: inferior or unproven (lower <= -3 pp)')
    assert s.startswith('**Drill training on D2 + D3') and 'Verdict:** inferior' in s and 'range -7.02 to +0.35' in s, s
    assert readable('plain note') == 'plain note'
    assert readable('Weekend pod queue: weekend queue done (1.1G)').startswith('First half')
    print(s); print('fmt self-check passed')
