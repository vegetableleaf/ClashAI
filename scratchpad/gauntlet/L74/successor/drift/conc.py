import sys
sys.path.insert(0, '.')
import drift as D
for nm, path, kind in (('train', D.TRAIN, 'train'), ('d3', D.D3, 'd3'), ('exploit', D.EXPLOIT, 'x')):
    rows = sorted(D.pool(path, kind), key=lambda x: -x[1])
    eff = 1 / sum(q * q for _, q in rows)
    top10 = sum(q for _, q in rows[:10]); top50 = sum(q for _, q in rows[:50])
    print(f"{nm}: {len(rows)} decks, effective {eff:.0f}, top10 {100*top10:.1f}%, top50 {100*top50:.1f}%")
    for eng, q in rows[:6]:
        print(f"   {100*q:.2f}% {D.A.classify(eng):12s} {', '.join(eng)}")
