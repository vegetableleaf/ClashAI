"""F635 sweep decks, one pair per hero form (a hero-form row with a LinkedChampionCharacter: the ones with an ability) and per champion of the Ladder pool (Census.ladderCards rules):
python3 forms_decks.py TABLES_DIR census_decks.tsv > forms_decks.tsv
Side 0 = our deck (the census's side 0). Side 1 = the first census opponent deck that carries the form, else the form's
card at index 1 (hero flag 2; a champion flag 0) with seven fillers. id = the form."""
import json, sys

T = sys.argv[1]
rows = {t: json.load(open('%s/%s.json' % (T, t)))['rows'] for t in
        ('spells_characters', 'spells_buildings', 'spells_other', 'spells_hero_form')}
SKIP = {'Snowball', 'WarmSpell', 'TriWizards', 'PrinceBuff', 'MergeMaiden_Mounted', 'MergeMaiden_Normal',
        'GoblinPartyHut', 'GoblinPartyRocket', 'MinionGiant', 'WitchMother'}
pool, champ = [], set()
for t in ('spells_characters', 'spells_buildings', 'spells_other'):
    for n, r in rows[t].items():
        c = r['columns']
        if c.get('NotInUse') or c.get('ManaCost') is None or not (c.get('Rarity') or ''):
            continue
        if n.startswith(('Super', 'Global')) or n.endswith(('_Chess', '_SpookyChess')) or n in SKIP:
            continue
        pool.append(n)
        if c['Rarity'] == 'Champion':
            champ.add(n)
census = [l.rstrip('\n').split('\t') for l in open(sys.argv[2]) if l.strip() and not l.startswith('#')]
ours = census[0][1:3]
FILL = ['Knight', 'Archer', 'Fireball', 'Zap', 'Musketeer', 'Giant', 'Valkyrie', 'Skeletons', 'Bomber']
chars = json.load(open(T + '/characters.json'))['rows']


def has_ability(card):
    """A hero form whose champion link, or whose summoned character, has an ability row."""
    c = rows['spells_hero_form'].get(card + '_hero', {}).get('columns', {})
    if c.get('LinkedChampionCharacter'):
        return True
    for unit in [c.get('SummonCharacter') or ''] + list(c.get('SummonCharactersList') or []):
        if unit and (chars.get(unit, {}).get('columns', {}).get('Ability') or ''):
            return True
    return False


forms = [(c, 2) for c in pool if has_ability(c)] + [(c, 0) for c in sorted(champ)]
for card, flag in forms:
    form = card + '_hero' if flag == 2 else card
    deck = None
    for r in census:
        d, s = r[3].split(','), list(map(int, r[4].split(',')))
        if card in d and (flag == 0 or s[d.index(card)] == 2):
            deck = r[3:5]
            break
    if deck is None:
        d = [FILL[0], card] + [f for f in FILL[1:] if f != card][:6]
        deck = [','.join(d), ','.join(['0', str(flag)] + ['0'] * 6)]
    print('\t'.join([form] + ours + deck))
