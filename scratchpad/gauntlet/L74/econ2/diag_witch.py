"""Why do live logs show 1.67 Witch bodies per 1x minute (SIM .45)? Per match: Witch first sightings, ids, lifetime in states,
and the first-sighting y. python diag_witch.py [card]"""
import sys, collections
import econ2 as E


def main(card):
    E.G.load_catalog()
    ms = [m for m in E.load("live") if not any(p[1] not in E.CARDS for p in m["pl"])]
    per = []
    for m in ms:
        d = [x for x in m.get("dep", []) if x[1] == card]
        if d: per.append((len(d), m["file"], [round(x[0] / 20) for x in d][:12], [x[3] for x in d][:12]))
    per.sort(reverse=True)
    print(card, "matches with it", len(per), "of", len(ms), "| sightings per such match", collections.Counter(min(p[0], 10) for p in per))
    for p in per[:8]: print(p)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Witch")
