import glob, sys, xml.etree.ElementTree as ET
t = f = e = s = 0
for p in glob.glob(sys.argv[1] + "/*.xml"):
    r = ET.parse(p).getroot()
    t += int(r.get("tests")); f += int(r.get("failures")); e += int(r.get("errors")); s += int(r.get("skipped"))
print("tests", t, "failures", f, "errors", e, "skipped", s)
