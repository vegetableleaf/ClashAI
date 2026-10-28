import java.lang.invoke.*;
import jdk.incubator.foreign.*;
public class Libm {
  static final MethodHandle EXP, POW;
  static {
    CLinker l = CLinker.getInstance();
    var fd1 = FunctionDescriptor.of(CLinker.C_DOUBLE, CLinker.C_DOUBLE);
    var fd2 = FunctionDescriptor.of(CLinker.C_DOUBLE, CLinker.C_DOUBLE, CLinker.C_DOUBLE);
    EXP = l.downcallHandle(CLinker.systemLookup().lookup("exp").get(), MethodType.methodType(double.class, double.class), fd1);
    POW = l.downcallHandle(CLinker.systemLookup().lookup("pow").get(), MethodType.methodType(double.class, double.class, double.class), fd2);
  }
  public static double exp(double x) { try { return (double) EXP.invokeExact(x); } catch (Throwable t) { throw new RuntimeException(t); } }
  public static double pow(double x, double y) { try { return (double) POW.invokeExact(x, y); } catch (Throwable t) { throw new RuntimeException(t); } }
  public static void main(String[] a) throws Exception {
    int en = 0, ee = 0, sn = 0, se = 0, pn = 0, pe = 0;
    for (String line : java.nio.file.Files.readAllLines(java.nio.file.Path.of("fp_in.txt"))) {
      String[] f = line.split(" ");
      if (f[0].equals("E")) { en++; if (exp(FpProbe.d(f[1])) == FpProbe.d(f[3])) ee++; }
      if (f[0].equals("S")) { sn++; if (pow(FpProbe.d(f[1]), 0.5) == FpProbe.d(f[2])) se++; }
      if (f[0].equals("P")) { pn++; if (pow(FpProbe.d(f[1]), FpProbe.d(f[2])) == FpProbe.d(f[3])) pe++; }
    }
    System.out.printf("FFI exp %d/%d  pow(.5) %d/%d  pow %d/%d%n", ee, en, se, sn, pe, pn);
    long t = System.nanoTime(); double s = 0; for (int i = 0; i < 10_000_000; i++) s += pow(1e6 + i, 0.5);
    System.out.printf("pow ns/call %.1f (%s)%n", (System.nanoTime() - t) / 1e7, s);
  }
}
