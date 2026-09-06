"""Patched crawl_deck/crawl_icebow parse_replay_ext must equal refetch_i1.parse_replay_i1 on i=0 and i=1 payloads."""
import sys, glob, os, importlib.util
sys.path.insert(0, r'C:\Users\benpe\clash-replay-scraper')
import crawl_deck, crawl_icebow
spec = importlib.util.spec_from_file_location('refetch_i1', r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L64\xy_why\refetch\refetch_i1.py')
refetch_i1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(refetch_i1)
files = [r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L64\xy_why\refetch\00YYPYJ2GPUU.html']
files += sorted(glob.glob(r'C:\Users\benpe\ClashBot\hogeq\data\royaleapi\crawl2\payloads\*.html'))[:3]
files += [r'C:\Users\benpe\ClashBot\icebow\data\royaleapi\crawl2\probe_payload.html']  # i=0 payload (02GY9GQLLQ2Y)
for f in files:
    h = open(f, encoding='utf-8').read()
    ref = refetch_i1.parse_replay_i1(h)
    for mod in (crawl_deck, crawl_icebow):
        _, p = mod.parse_replay_ext(h)
        key = lambda r: (r.get('x_units'), r.get('y_units'), r.get('attr_i'))
        same = len(p) == len(ref) and all(key(a) == key(b) for a, b in zip(p, ref))
        print(os.path.basename(f), mod.__name__, 'rows', len(p), 'with xy', sum(bool(r.get('x_units')) for r in p),
              'i', sorted(set(r.get('attr_i') for r in p)), 'MATCH' if same else 'DIFF')
