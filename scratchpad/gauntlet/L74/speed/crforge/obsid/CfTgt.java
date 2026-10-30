// TARGET-OBS (plan1026/target_obs/TARGET_OBS.md, M2 "Java fast loop"): production's target rows (the GenModel keys
// "tgt" [64, 8] float32 + "tgt_idx" [64] int64) in Java, on the F1 facade's battle. Production
// (pipeline/target_obs.sim_target_rows) = sim_unit_state.extract over the facade (attack.target = CfCore.acquired via
// cueSave) -> target_obs.target_rows on the prepared tok / mask. This class reads the same facade values CfCue does
// (CfCue.units, CfCore.acquired, the attack timer, the card table's hit speed) and repeats target_rows line for line.
//
// Call only after CfCue.build returned true on the same state with the same Tables (every body row name is then in T).

import java.nio.ByteBuffer;
import java.nio.FloatBuffer;
import java.nio.LongBuffer;
import java.util.ArrayList;
import java.util.HashMap;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.target.TargetView;

public final class CfTgt {
  private CfTgt() {}

  public static final int N = 8, U = CfCue.U, TOK = CfCue.TOK;   // target_obs.TGT_N

  /** The target id of a body (CfCue.vector's tgt: CfCore.acquired -> entity id), -1 = none. */
  static int target(CfCore core, WorldEntity w) {
    TargetView ref = CfCore.acquired(w);
    if (ref == null) return -1;
    WorldEntity te = core.s.std.getWorld().entityOf(ref.getEntity());
    return te == null ? -1 : te.getId();
  }

  /** target_obs._board: engine milli-tiles -> this seat's token frame (seat 1 mirrored), CfCue's arithmetic. */
  static double bx(WorldEntity w, int seat) { double b = w.x() / 1000.0 / 18.0; return seat == 1 ? 1.0 - b : b; }
  static double by(WorldEntity w, int seat) { double b = 1.0 - w.y() / 1000.0 / 32.0; return seat == 1 ? 1.0 - b : b; }

  /** target_rows(units, tok, mask, seat) into {@code out} [64 * 8] floats and {@code idx} [64] longs. */
  public static void build(CfCore core, int seat, CfCue.Tables T, FloatBuffer tok, int tokOff, ByteBuffer mask,
      int maskOff, FloatBuffer out, int outOff, LongBuffer idx, int idxOff) {
    for (int i = 0; i < U * N; i++) out.put(outOff + i, 0f);
    for (int i = 0; i < U; i++) idx.put(idxOff + i, -1L);
    ArrayList<WorldEntity> us = CfCue.units(core);
    if (us.isEmpty()) return;                                  // "if not units"
    HashMap<Integer, WorldEntity> byId = new HashMap<>();
    ArrayList<WorldEntity> bodies = new ArrayList<>();
    for (WorldEntity w : us) {
      byId.put(w.getId(), w);
      if (!(w instanceof TowerEntity)) bodies.add(w);
    }
    bodies.sort((p, q) -> Integer.compare(p.getId(), q.getId()));   // extract's units.sort(uid)
    // token_match = CfCue.build's match, verbatim. ponytail: a copy (CfCue stays byte-identical untouched); the
    // identity run (compare.py, tgt / tgt_idx bytes) fails if the two drift.
    HashMap<Integer, Integer> tokOf = new HashMap<>();         // body uid -> token index
    int[] ti = new int[U];
    int nt = 0;
    for (int i = 0; i < U; i++) {
      int o = tokOff + i * TOK;
      if (mask.get(maskOff + i) != 0 && tok.get(o + 13) == 0f && (tok.get(o + 1) > 0f || tok.get(o + 2) > 0f)) ti[nt++] = i;
    }
    int nb = bodies.size();
    if (nt > 0 && nb > 0) {
      double[] bx = new double[nb], by = new double[nb];
      boolean[] mine = new boolean[nb];
      for (int j = 0; j < nb; j++) {
        WorldEntity w = bodies.get(j);
        bx[j] = bx(w, seat);
        by[j] = by(w, seat);
        mine[j] = w.side() == seat;
      }
      double[] d = new double[nt * nb];
      for (int i = 0; i < nt; i++) {
        int o = tokOff + ti[i] * TOK;
        double tx = tok.get(o + 4), ty = tok.get(o + 5);
        boolean tm = tok.get(o + 1) > 0f;
        for (int j = 0; j < nb; j++)
          d[i * nb + j] = tm != mine[j] ? Double.POSITIVE_INFINITY : Math.hypot((tx - bx[j]) * 18.0, (ty - by[j]) * 32.0);
      }
      while (true) {                                           // np.argmin: the first minimum in row-major order
        int best = 0;
        for (int q = 1; q < d.length; q++) if (d[q] < d[best]) best = q;
        if (!(d[best] <= CfCue.MATCH_TILES)) break;
        int i = best / nb, j = best % nb;
        tokOf.put(bodies.get(j).getId(), ti[i]);
        for (int q = 0; q < nb; q++) d[i * nb + q] = Double.POSITIVE_INFINITY;
        for (int q = 0; q < nt; q++) d[q * nb + j] = Double.POSITIVE_INFINITY;
      }
    }
    if (tokOf.isEmpty()) return;                               // no matched token: every row stays 0 / -1
    HashMap<Integer, Integer> tgt = new HashMap<>();           // uid -> target uid (-1 none), every unit
    for (WorldEntity w : us) tgt.put(w.getId(), target(core, w));
    for (WorldEntity u : us) {                                 // incoming: who targets each matched token
      Integer t = tokOf.get(tgt.get(u.getId()));
      if (t == null) continue;
      if (u instanceof TowerEntity) out.put(outOff + t * N + 7, 1f);
      else if (tokOf.containsKey(u.getId())) out.put(outOff + t * N + 6, out.get(outOff + t * N + 6) + 0.25f);
    }
    for (WorldEntity b : bodies) {
      Integer t = tokOf.get(b.getId());
      if (t == null) continue;
      int o = outOff + t * N, tg = tgt.get(b.getId());
      int[] ct = T.body.get(b.getData().name());
      if (ct == null) throw new IllegalStateException("CfTgt before CfCue filled body row " + b.getData().name());
      int hs = ct[0], prog = b.getTargeting().getAttackTimerMs();
      boolean phase = tg >= 0 && prog > 0;                     // extract: phase != 'idle'
      out.put(o, 1f);
      out.put(o + 3, hs != 0 && phase ? (float) CfCue.round3((double) (prog % hs) / hs) : 0f);
      WorldEntity tu = tg >= 0 ? byId.get(tg) : null;
      if (tu == null) continue;
      if (tu instanceof TowerEntity) out.put(o + 2, 1f);
      else if (tokOf.containsKey(tg)) {
        out.put(o + 1, 1f);
        idx.put(idxOff + t, tokOf.get(tg));
      }
      out.put(o + 4, (float) (bx(tu, seat) - bx(b, seat)));
      out.put(o + 5, (float) (by(tu, seat) - by(b, seat)));
    }
  }
}
