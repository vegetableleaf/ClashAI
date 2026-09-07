import re,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
for f in sys.argv[1:]:
    print("=====",f)
    for l in open(f,encoding="utf-8"):
        l=l.rstrip()
        if not l: continue
        if len(re.findall(r'[一-鿿]',l))>5: continue
        print(l)
