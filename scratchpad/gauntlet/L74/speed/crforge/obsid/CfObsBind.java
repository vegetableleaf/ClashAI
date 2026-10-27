// S3b-3a (plan1026 Pillar 4): CfSpeed.Match's observation builder reading the F1 facade's battle (CfCore), for
// obs_id.py. CfSpeed, CfCore and this class share the default package, so the facade's package-private St.std is
// reachable here and nowhere in Python. The facade steps the battle; the builder only reads it.

import java.util.Arrays;

public final class CfObsBind {
  private CfObsBind() {}

  /**
   * Points {@code m} at the facade's current battle (a reset or a load makes a new one: the age table restarts) and
   * sets {@code seat}'s engine deck index -> our deck slot map (8 = none).
   */
  public static void bind(CfSpeed.Match m, CfCore core, int seat, int[] slotOf) {
    if (m.std != core.s.std) {
      m.std = core.s.std;
      Arrays.fill(m.firstSeen, -1);
      m.firstOther.clear();
    }
    System.arraycopy(slotOf, 0, seat == 0 ? m.slotOf0 : m.slotOf1, 0, 8);
  }
}
