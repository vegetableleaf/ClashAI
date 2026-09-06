"""Repair the two crawl CSVs that crawl_par.py's merge wrote with the wrong field lists (L64p).

Two writer bugs, both caught by the drive failing on every new tag with KeyError on attr_s:

  plays_ext.csv  -- the file's header is 12 columns and has NO attr_i (that column lives only in
                    plays_ext_i1.csv). crawl_par wrote 13 fields with attr_i in the middle, so every
                    new row is shifted: the attr_s column holds attr_i, attr_t holds attr_s, and
                    attr_t spills into a 13th unnamed column. Values are intact, only mislabelled.
                    Repair: move those rows to plays_ext_i1.csv (13 columns, attr_i LAST) in that
                    file's own order, and drop them from plays_ext.csv.

  battles.csv    -- pipeline.BATTLE_FIELDS already ENDS with "plays"; crawl_par appended it again,
                    so DictWriter emitted the value twice. The duplicate is last, so columns 0..28
                    are correct and only a trailing 30th value is spurious. Repair: truncate.

Writes NEW files and swaps them in; .bak_L64p copies of all three were taken first.
"""
import csv
from pathlib import Path

D = Path("icebow/data/royaleapi/crawl2")
PLAYS, I1, BATTLES = D / "plays_ext.csv", D / "plays_ext_i1.csv", D / "battles.csv"

# --- plays_ext.csv: split the shifted rows out ------------------------------------------------
with PLAYS.open(encoding="utf-8", newline="") as f:
    rd = csv.reader(f)
    p_hdr = next(rd)
    keep, moved = [], []
    for row in rd:
        (keep if len(row) == len(p_hdr) else moved).append(row)
print("plays_ext.csv: %d good rows, %d shifted rows to move" % (len(keep), len(moved)))
assert all(len(r) == 13 for r in moved), "unexpected row width among the shifted rows"

with I1.open(encoding="utf-8", newline="") as f:
    i1_hdr = next(csv.reader(f))
print("plays_ext_i1.csv header:", i1_hdr)

# crawl_par's write order -> the i1 file's order. Only the last three differ.
MINE = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y",
        "attr_ability", "attr_card", "attr_i", "attr_s", "attr_t"]
idx = [MINE.index(c) for c in i1_hdr]
fixed = [[r[i] for i in idx] for r in moved]

# sanity: attr_s must be blue/red again, attr_i must be 0/1
ss = {r[i1_hdr.index("attr_s")] for r in fixed}
ii = {r[i1_hdr.index("attr_i")] for r in fixed}
print("after remap -- attr_s values:", sorted(ss), "| attr_i values:", sorted(ii))
assert ss <= {"blue", "red"}, "attr_s still wrong after remap: %s" % sorted(ss)
assert ii <= {"0", "1", ""}, "attr_i still wrong after remap: %s" % sorted(ii)

tmp = PLAYS.with_suffix(".csv.fixed")
with tmp.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(p_hdr); w.writerows(keep)
tmp.replace(PLAYS)

existing = {r[0] for r in csv.reader(I1.open(encoding="utf-8", newline=""))}
with I1.open("a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    n = 0
    for r in fixed:
        w.writerow(r); n += 1
print("moved %d rows into plays_ext_i1.csv (%d tags already there)" % (n, len(existing)))

# --- battles.csv: drop the duplicated trailing "plays" -----------------------------------------
with BATTLES.open(encoding="utf-8", newline="") as f:
    rd = csv.reader(f)
    b_hdr = next(rd)
    rows, trimmed = [], 0
    for row in rd:
        if len(row) == len(b_hdr) + 1:
            assert row[-1] == row[-2], "battles row 30th value is not the duplicate: %r" % row[-2:]
            row = row[:-1]; trimmed += 1
        rows.append(row)
print("battles.csv: trimmed %d rows of %d" % (trimmed, len(rows)))
tmp = BATTLES.with_suffix(".csv.fixed")
with tmp.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(b_hdr); w.writerows(rows)
tmp.replace(BATTLES)
print("repair complete")
