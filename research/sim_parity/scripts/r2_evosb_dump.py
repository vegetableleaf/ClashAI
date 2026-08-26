"""Dump the analyst-relevant parts of a cached evolution page: vardefines, infobox,
non-formula table rows, attribute tables, and the History section."""
import re, sys

fn = sys.argv[1]
txt = open("C:/Users/benpe/ClashBot/research/sim_parity/webcache/" + fn, encoding="utf-8").read()

print("== VARDEFINES ==")
for m in re.finditer(r"\{\{#vardefine:\s*([^|]+?)\s*\|\s*([^}]+?)\s*\}\}", txt):
    print(f"  {m.group(1)} = {m.group(2)}")

print("== INFOBOX/TEMPLATES (first 3 lines of each {{...Infobox...}}) ==")
for m in re.finditer(r"\{\{[^{}]*Infobox[^{}]*\}\}", txt):
    print("  " + m.group(0)[:400])

print("== TABLE LINES (headers + literal-value rows, skipping #expr formula rows) ==")
in_table = False
for line in txt.split("\n"):
    if line.startswith("{|"):
        in_table = True; print("  ---TABLE---")
    if in_table:
        if "#expr" in line or "#var" in line:
            pass
        elif line.startswith(("!", "|", "{|", "|}")):
            print("  " + line[:300])
    if line.startswith("|}"):
        in_table = False

print("== SECTION HEADERS ==")
for m in re.finditer(r"^==+.*?==+$", txt, re.M):
    print("  " + m.group(0))

print("== HISTORY ==")
h = re.search(r"==\s*History\s*==(.*?)(?:\n==[^=]|\Z)", txt, re.S)
if h:
    print(h.group(1).strip()[:6000])
else:
    print("  (none)")
