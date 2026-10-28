import java.nio.file.*; import java.util.*;
public class FpProbe {
  static double d(String s) { return Double.longBitsToDouble(Long.parseUnsignedLong(s, 16)); }
  public static void main(String[] a) throws Exception {
    int[] dn = new int[4]; int en = 0, es = 0, em = 0, sn = 0, ss = 0, pn = 0, ps = 0, pm = 0, ef = 0;
    for (String line : Files.readAllLines(Path.of("fp_in.txt"))) {
      String[] f = line.split(" ");
      switch (f[0]) {
        case "D" -> { double s = 0, t = 0; for (int i = 0; i < 14; i++) { s += d(f[1 + i]) * d(f[15 + i]); t = Math.fma(d(f[1 + i]), d(f[15 + i]), t); }
                      double np = d(f[29]); dn[0]++; if (s == np) dn[1]++; if (t == np) dn[2]++; }
        case "E" -> { double x = d(f[1]); en++; if (StrictMath.exp(x) == d(f[3])) es++; if (Math.exp(x) == d(f[3])) em++; if (StrictMath.exp(x) == d(f[2])) ef++; }
        case "S" -> { sn++; if (Math.sqrt(d(f[1])) == d(f[2])) ss++; }
        case "P" -> { pn++; double r = d(f[3]); if (StrictMath.pow(d(f[1]), d(f[2])) == r) ps++; if (Math.pow(d(f[1]), d(f[2])) == r) pm++; }
      }
    }
    System.out.printf("dot n=%d seqNoFMA==numpy %d  seqFMA==numpy %d%n", dn[0], dn[1], dn[2]);
    System.out.printf("exp n=%d StrictMath==math.exp %d  Math==math.exp %d  StrictMath==np.exp %d%n", en, es, em, ef);
    System.out.printf("sqrt n=%d Math.sqrt==py pow(.5) %d%n", sn, ss);
    System.out.printf("pow n=%d StrictMath==py %d  Math==py %d%n", pn, ps, pm);
  }
}
