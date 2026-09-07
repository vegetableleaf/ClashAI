p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''    ap.add_argument("--off", type=float, default=0.5, help="cell->point offset; 0.5 = cell centre")''',
'''    ap.add_argument("--off", type=float, default=0.5, help="cell->point offset; 0.5 = cell centre")
    # The 500-state bench is built from the v3 dataset, whose replays were driven from plays_ext.csv.
    # plays_ext_i1.csv holds only the LATER refetch (0 rows for the bench's tags), so pointing at it
    # yields "battles.csv says 55 plays, ... has 0" -- an error whose text names the default file, not
    # the one actually being read, which is why it does not point at its own cause.
    ap.add_argument("--plays-file", default="plays_ext.csv")
    ap.add_argument("--crawl", default="icebow")''')
s = s.replace('''    rd.set_crawl("icebow")
    rd.set_plays_file("plays_ext_i1.csv")''',
'''    rd.set_crawl(a.crawl)
    rd.set_plays_file(a.plays_file)''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
