"""Enemy body names in compact SIM / live data that the unit-value table does not know (valued at the 0.5 default), by sightings.
python diag_names.py sim_de10"""
import sys, collections
import econ2 as E
G = E.G


def main(n):
    G.load_catalog(); c = collections.Counter(); known = collections.Counter()
    for m in E.load(n):
        for d in m.get("dep", []):
            t, card = d[0], d[1]
            (known if card in G.UV or card in G.NCOST else c)[card] += 1
    print(n, "unknown names (first sightings):", c.most_common(30))
    print(n, "known top:", [(k, v, G.uval(k)) for k, v in known.most_common(40)])


if __name__ == "__main__":
    main(sys.argv[1])
