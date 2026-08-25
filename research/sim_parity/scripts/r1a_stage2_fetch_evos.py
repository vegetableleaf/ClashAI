# -*- coding: utf-8 -*-
"""r1a stage 2: fetch each existing Evolution subpage, archive wikitext, capture revid,
extract release documentation + cycles. Also parse master-page cycles table as cross-check."""
import json, time, re, urllib.request, urllib.parse, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDRS = {"User-Agent": "icebow-monitor/1.0 (+local)"}
WEBCACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache/"
LEDGER = "C:/Users/benpe/ClashBot/research/sim_parity/ledger/"

def api(params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(BASE + "?" + qs, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    time.sleep(0.2)
    return data

stage1 = json.load(open(LEDGER + "r1a_stage1.json", encoding="utf-8"))
existing = stage1["evo_existing"]
failures = []
results = {}

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
date_pat = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})|((?:%s)\s+\d{1,2},?\s+\d{4})|(\d{1,2}\s+(?:%s)\s+\d{4})" % (MONTHS, MONTHS))

for title in existing:
    try:
        d = api({"action": "parse", "page": title, "prop": "wikitext|revid", "format": "json"})
        wt = d["parse"]["wikitext"]["*"]
        revid = d["parse"]["revid"]
    except Exception as e:
        failures.append(f"{title}: {e!r}")
        continue
    fn = WEBCACHE + title.replace("/", "_").replace(" ", "_") + ".wikitext"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(wt)

    # cycles: infobox param or 'Cycles' mention
    cycles = None
    m = re.search(r"\|\s*cycles?\s*=\s*(\d+)", wt, re.I)
    if m: cycles = int(m.group(1))
    if cycles is None:
        m = re.search(r"(\d+)\s*Cycles?", wt)
        if m: cycles = int(m.group(1))

    # release documentation: lines mentioning released/release/added with a date
    rel_lines = []
    for line in wt.splitlines():
        ll = line.lower()
        if ("releas" in ll or "was added" in ll or "were added" in ll or "unveil" in ll or "announc" in ll) :
            if len(line) < 600:
                rel_lines.append(line.strip())
    # first date found in release lines
    rel_date = None
    for line in rel_lines:
        if "releas" in line.lower() or "added" in line.lower():
            m = date_pat.search(line)
            if m:
                rel_date = m.group(0)
                rel_line = line
                break
    unreleased = bool(re.search(r"not (yet )?(been )?released|upcoming|unreleased|will be released", wt, re.I))
    results[title] = {"revid": revid, "cycles": cycles, "release_date_raw": rel_date,
                      "release_lines": rel_lines[:6], "unreleased_flag": unreleased,
                      "wikitext_len": len(wt), "cache_file": fn}
    print(f"{title}: revid={revid} cycles={cycles} rel={rel_date} unreleased_flag={unreleased}")

# master page cycles cross-check
mwt = open(WEBCACHE + "Card_Evolution.wikitext", encoding="utf-8").read()
rows = re.split(r"\n\|-\s*\n", mwt)
master_cycles = {}
for row in rows:
    m = re.match(r"\|\[\[([^/|]+)/Evolution\|", row.strip())
    if m:
        card = m.group(1)
        cells = [c.strip() for c in re.split(r"\n\|", row) if c.strip()]
        # cells: [cardcell, cost, cycles, totalcost, statboost, ability]
        if len(cells) >= 3 and re.match(r"^\d+$", cells[2]):
            master_cycles[card] = int(cells[2])
print("master table cycles entries:", len(master_cycles))

out = {"fetched": "2026-08-25", "pages": results, "master_cycles": master_cycles, "failures": failures}
with open(LEDGER + "r1a_stage2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("FAILURES:", failures)
