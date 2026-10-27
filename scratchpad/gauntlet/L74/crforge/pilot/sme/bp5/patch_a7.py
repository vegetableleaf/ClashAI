s = open('AimRun7.java').read()
a = """        int W = w.getGrid().getWidth();
        for (int dr = -1; dr <= 1; dr++)"""
b = """        int W = w.getGrid().getWidth();
        var hr = ce.getUnit().movement().getRoute();
        StringBuilder hs = new StringBuilder("[\\"held\\",").append(id);
        for (int i = 0; i < hr.size(); i++) hs.append(',').append(hr.get(i));
        EV.get().add(hs.append(']').toString());
        for (int dr = -1; dr <= 1; dr++)"""
assert s.count(a) == 1
open('AimRun7.java', 'w').write(s.replace(a, b))
