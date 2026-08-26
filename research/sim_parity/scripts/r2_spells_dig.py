import re, sys, os
CACHE = r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
NOISE = re.compile(r"arena|card render|Level [Cc]ap|Mastery|emote|sound effect|Star Level|"
                   r"Shop|chest|deck|icon|description|Trivia|translat|Draft|Challenge", re.I)
def clean(s):
    s = re.sub(r"\{\{Icon\|[^}]*\}\}", "", s)
    s = re.sub(r"<br\s*/?>", " / ", s)
    s = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{Balance\|\w+\}\}", "", s)
    return s.strip()
def extract(title, hist_all=False):
    fn = os.path.join(CACHE, title.replace("/", "_").replace(" ", "_") + ".wikitext")
    txt = open(fn, encoding="utf-8").read()
    print("=" * 25, title, "=" * 25)
    print("-- INFOBOX/LEAD --")
    for m in re.finditer(r"\{\{Card Infobox[^}]*\}\}", txt):
        print("  " + m.group(0))
    for m in re.finditer(r"\{\{Quote\|(.*?)\}\}", txt, re.S):
        print("  QUOTE: " + clean(m.group(1))[:400])
    lead = re.search(r"\n\nThe .{0,1200}?\n", txt, re.S)
    if lead: print("  LEAD: " + clean(lead.group(0))[:900])
    print("-- P1 vardefines --")
    for m in re.finditer(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", txt):
        print(f"  {m.group(1)} = {m.group(2)}")
    print("-- P2 tables --")
    for tm in re.finditer(r"\{\|[^\n]*\n(.*?)\n\|\}", txt, re.S):
        head = tm.group(0)[:80].replace("\n", " ")
        print(f"  [TABLE {head}]")
        rows = [clean(l.strip()) for l in tm.group(1).splitlines()
                if l.strip().startswith(("!", "|")) and not l.strip().startswith("|}")]
        for r in rows[:14]:
            if r and r != "|-": print("    " + r[:250])
    print("-- P3 history --")
    m = re.search(r"==\s*History\s*==(.*?)(?:\n==[^=]|\Z)", txt, re.S)
    if m:
        for line in m.group(1).splitlines():
            s = line.strip()
            if s.startswith("*"):
                c = clean(s)
                if hist_all or not NOISE.search(c):
                    print("  " + c[:340])
    else: print("  (no History section)")
for t in sys.argv[1:]:
    extract(t)
