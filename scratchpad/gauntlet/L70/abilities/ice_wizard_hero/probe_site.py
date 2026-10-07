"""Public-page probe (clearance only, no login): what does RoyaleAPI list for ice-wizard-hero decks?"""
import sys, re, json
sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale import parse, pipeline
from royale.transport import Pages, Curl
from royale.cookies import Session
pages = Pages()
curl = Curl(pages, Session("none", ""))
SEED = "ice-wizard-hero,knight-ev1,rocket,skeletons,tesla-ev1,the-log,tornado,x-bow"
try:
    html = curl.get(f"/decks/stats/{SEED}/similar")
    decks = parse.similar_decks(html, SEED)
    print("similar", len(decks))
    for d in decks: print("  ", d)
    open("probe_similar.html", "w", encoding="utf-8").write(html)
    # card page candidates
    for p in ["/cards/ice-wizard-hero", "/card/ice-wizard-hero", "/decks/popular?inc=ice-wizard-hero"]:
        try:
            h = curl.get(p); print(p, "OK", len(h), len(re.findall(r"/decks/stats/([a-z0-9,\-]+)", h)))
            open("probe_" + re.sub(r"\W", "_", p) + ".html", "w", encoding="utf-8").write(h)
        except Exception as e:
            print(p, "ERR", type(e).__name__, str(e)[:100])
finally:
    pages.close()
