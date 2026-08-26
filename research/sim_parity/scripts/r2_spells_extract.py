import re, sys, os
CACHE = os.path.join(os.path.dirname(__file__), "..", "webcache")

def extract(title):
    fn = os.path.join(CACHE, title.replace("/", "_").replace(" ", "_") + ".wikitext")
    txt = open(fn, encoding="utf-8").read()
    print("=" * 20, title, "=" * 20)
    print("--- P1 vardefines ---")
    for m in re.finditer(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", txt):
        print(f"  {m.group(1)} = {m.group(2)}")
    print("--- P2 attributes table ---")
    m = re.search(r'id="unit-attributes-table".*?\|\}', txt, re.S)
    if m:
        for line in m.group(0).splitlines():
            line = line.strip()
            if line.startswith("!") or (line.startswith("|") and not line.startswith("|}")):
                line = re.sub(r"\{\{Icon\|I=[^}]*\}\}", "", line)
                line = re.sub(r"<br\s*/?>", " ", line)
                print("  " + line)
    else:
        print("  (no unit-attributes-table)")
    print("--- P3 history (dated entries) ---")
    m = re.search(r"==\s*History\s*==(.*?)(?:\n==[^=]|\Z)", txt, re.S)
    if m:
        hist = m.group(1)
        for line in hist.splitlines():
            s = line.strip()
            if s.startswith("*") or s.startswith("|"):
                print("  " + s[:400])
    else:
        print("  (no History section)")

for t in sys.argv[1:]:
    extract(t)
