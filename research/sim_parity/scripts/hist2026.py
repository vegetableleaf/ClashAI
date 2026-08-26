import re, os, json, sys
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
PAGES = json.load(open(r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_a_livecheck.json", encoding="utf-8"))

def clean(s):
    s = re.sub(r'\[\[:?[^|\]]*\|([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\{\{Balance\|[^}]*\}\}', '', s)
    s = re.sub(r'\{\{Rarity\|([^}]*)\}\}', r'\1', s)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    return re.sub(r'\s+', ' ', s).strip()

YEARS = sys.argv[1:] or ["2025", "2026"]
for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    m = re.search(r'\n==\s*History\s*==\s*\n(.*?)(?=\n==[^=]|\Z)', t, re.S)
    if not m:
        print(f"### {title}: NO HISTORY SECTION"); continue
    h = m.group(1)
    # split into year blocks: a bare line that is just a year
    parts = re.split(r'\n(?=(?:19|20)\d\d\s*\n)', h)
    out = []
    for p in parts:
        y = re.match(r'((?:19|20)\d\d)', p.strip())
        if y and y.group(1) in YEARS:
            for line in p.split("\n"):
                if line.strip().startswith("*"):
                    out.append("   " + clean(line.lstrip("*").strip()))
    print(f"### {title}  [{', '.join(YEARS)}]")
    print("\n".join(out) if out else "   (no entries in these years)")
