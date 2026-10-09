"""Print the per-drill baseline table from out/baseline.json (+ D9 extra)."""
import json, sys
B = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'out/baseline.json'))
G = [g for g in ('live_current', 'live_deployed', 'live_all', 'pros', 'sim') if g in B]
print({g: (B[g]['matches'], B[g]['minutes']) for g in G})
for dr in sorted({d for g in G for d in B[g]['drills']}):
    for kind in ('do', 'do_kill6', 'hold', 'do_combo'):
        row = []
        for g in G:
            e = B[g]['drills'].get(dr, {}).get(kind)
            row.append(f"{g}: n={e['n']:5d} {e['pass_pct']:5.1f}% {e['ci']} {e['acts']}" if e else f"{g}: -")
        if any(not r.endswith('-') for r in row): print(dr, kind); [print('   ', r) for r in row]
for g in G: print(g, 'moments/match', B[g]['per_match'])
