"""mine_raw.txt (key | class | lever | why) + sample.txt cards -> mine.tsv (key, card, class, lever, why) for labels.py."""
card = {l.split('\t')[0]: l.split('\t')[1] for l in open('sample.txt')}
with open('mine.tsv', 'w', encoding='utf-8') as f:
    for l in open('mine_raw.txt', encoding='utf-8'):
        if l.startswith('#') or '|' not in l:
            continue
        k, c, lev, why = [x.strip() for x in l.split('|', 3)]
        f.write('\t'.join((k, card[k], c, lev, why)) + '\n')
