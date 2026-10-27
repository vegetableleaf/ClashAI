// S3b-4 (plan1026 Pillar 4b): CfSpeed.Rollout's loop on the F1 facade with EVERY ported observation builder on, for the
// cost of the full Java observation inside the loop. N facade matches (CfCore) per cohort on a pool of T threads; per
// 10-tick decision each seat acts (a Java stand-in policy: Rollout's javaPolicy rule, plus a rare ability press), the
// match steps, and both seats' rows are built into direct buffers at the live cfg (fv6, extrapolate 26, public counter):
//   tok / mask / sc / unit_form  CfObsBind.FacadeMatch (S3b-3a2 / -3e, sc[5] from CfOppElixir)
//   opp_past                     CfOppElixir (S3b-3c)
//   past + the 9 identity keys   CfIdent (S3b-3b)
//   projectiles / effects / own_ability / opp_cycle   CfPubObj (S3b-3d)
//   cue                          CfCue (S3b-3f), from the row's tok / mask
// Timing: thread CPU time (ThreadMXBean) around the engine part (acts + 10 ticks + resets) and the obs part, summed over
// the pool. The tables (names, detector keys, CfPubObj tables) are per cohort and filled from Python between rounds
// (cf_loop_obs.py); a decision that meets a missing key is counted (miss*) and finished with what is there.

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import org.crforge.core.battle.data.GameTables;

public final class CfLoop implements AutoCloseable {
  static final int CUE = 64 * 22, MAX_U = 64, F = 14, S = 70, PAST = 15, IDS = 48, PROJ = 64 * 8, EFF = 32 * 6, ABIL = 8 * 7, CYC = 8 * 4;
  static final ThreadMXBean MX = ManagementFactory.getThreadMXBean();

  public final int n, threads, decideEvery, extrap;
  final GameTables tables;
  final CfCore template;
  final String[][] decks;
  final int[][] forms, ids;
  final int[] inv = {0, 1, 2, 3, 4, 5, 6, 7};     // deal index -> our slot (identity: the stand-in decides by deal index)
  public final CfSpeed.Names names = new CfSpeed.Names();
  public final CfOppElixir.Keys keys = new CfOppElixir.Keys();
  public final CfPubObj.Tables pub = new CfPubObj.Tables();
  public final HashMap<Integer, Integer> gid = new HashMap<>();
  public CfCue.Tables cue;                        // S3b-3f's tables (Python sets it); null = cue not built
  public boolean buildObs = true;
  public double pPlay = 0.3, pPress = 0.05;

  final CfCore[] core;
  final CfObsBind.FacadeMatch[] m;
  final CfIdent[] id;
  final CfPubObj[] po;
  final long[] rng;
  CfCue.Seat[][] cueSeat;
  final AtomicInteger nextPair = new AtomicInteger(), seed = new AtomicInteger(1);
  final ExecutorService pool;
  Future<?> pending;

  public final ByteBuffer tokB, maskB, scB, formB, oppPastB, idsB, pastB, projB, effB, abilB, cycB, cueB;
  final FloatBuffer tok, sc, oppPast, past, proj, eff, abil, cyc, cueF;
  final LongBuffer idsL;
  public final AtomicLong matches = new AtomicLong(), ticks = new AtomicLong(), decisions = new AtomicLong(),
      plays = new AtomicLong(), presses = new AtomicLong(), engineNs = new AtomicLong(), obsNs = new AtomicLong(),
      rows = new AtomicLong(), missOpp = new AtomicLong(), missPub = new AtomicLong(), missCue = new AtomicLong(), crashes = new AtomicLong();
  public volatile String firstCrash;   // the first engine exception (a match crforge could not run, dropped)

  /** decks / forms / ids: 2 rows per pair (RoyaleSim names, forms, catalogue ids, in the deal order CfCore.reset takes). */
  public CfLoop(GameTables tables, CfCore template, String[][] decks, int[][] forms, int[][] ids, int n, int threads,
                int decideEvery, int extrap) {
    this.tables = tables; this.template = template; this.decks = decks; this.forms = forms; this.ids = ids;
    this.n = n; this.threads = threads; this.decideEvery = decideEvery; this.extrap = extrap;
    core = new CfCore[n]; m = new CfObsBind.FacadeMatch[n]; id = new CfIdent[n]; po = new CfPubObj[n]; rng = new long[n]; cueSeat = new CfCue.Seat[n][2];
    pool = Executors.newFixedThreadPool(threads, r -> { Thread t = new Thread(r, "cfloop"); t.setDaemon(true); return t; });
    long r2 = 2L * n;
    tokB = direct(r2 * MAX_U * F * 4); maskB = direct(r2 * MAX_U); scB = direct(r2 * S * 4); formB = direct(r2 * MAX_U);
    oppPastB = direct(r2 * PAST * 4); idsB = direct(r2 * IDS * 8); pastB = direct(r2 * PAST * 4);
    projB = direct(r2 * PROJ * 4); effB = direct(r2 * EFF * 4); abilB = direct(r2 * ABIL * 4); cycB = direct(r2 * CYC * 4); cueB = direct(r2 * CUE * 4);
    tok = tokB.asFloatBuffer(); sc = scB.asFloatBuffer(); oppPast = oppPastB.asFloatBuffer(); past = pastB.asFloatBuffer();
    proj = projB.asFloatBuffer(); eff = effB.asFloatBuffer(); abil = abilB.asFloatBuffer(); cyc = cycB.asFloatBuffer();
    idsL = idsB.asLongBuffer();
    cueF = cueB.asFloatBuffer();
    for (int i = 0; i < n; i++) {
      CfCore c = core[i] = new CfCore(tables);
      c.cardNames = template.cardNames;                    // the facade's identity tables (read-only), as CrforgeCore fills them
      c.unique.putAll(template.unique); c.uniqueCard.putAll(template.uniqueCard);
      c.byRoot.putAll(template.byRoot); c.spellObj.putAll(template.spellObj);
      m[i] = new CfObsBind.FacadeMatch(tables);
      m[i].extrap = extrap;
      id[i] = new CfIdent();
      id[i].extrap = extrap;
      po[i] = new CfPubObj(c, pub);
      po[i].extrap = extrap;
      rng[i] = 0x9E3779B97F4A7C15L * (i + 1);
    }
  }

  static ByteBuffer direct(long bytes) { return ByteBuffer.allocateDirect((int) bytes).order(ByteOrder.nativeOrder()); }

  public void putGid(int cardId, int g) { gid.put(cardId, g); }   // JPype would box a Python int key as a Long

  /** Before the first step: the checkpoint card ids (CfIdent's table) are in {@link #gid}. */
  public void start() {
    for (int i = 0; i < n; i++) { id[i].gid.putAll(gid); reset(i); }
  }

  void reset(int i) {
    int p = nextPair.getAndIncrement() % (decks.length / 2);
    int[] lv = {16, 16, 16, 16, 16, 16, 16, 16};
    core[i].reset(seed.getAndIncrement() & 0x7FFFFFFF, decks[2 * p], forms[2 * p], decks[2 * p + 1], forms[2 * p + 1], lv, lv,
        16, 16, ids[2 * p], ids[2 * p + 1]);
    cueSeat[i][0] = new CfCue.Seat(); cueSeat[i][1] = new CfCue.Seat();   // production: a fresh Match per match
  }

  long next(int i) { long x = rng[i]; x ^= x >>> 12; x ^= x << 25; x ^= x >>> 27; rng[i] = x; return x * 0x2545F4914F6CDD1DL; }

  double unit(int i) { return (next(i) >>> 11) * 0x1.0p-53; }

  void stepEnv(int i) {
    long t0 = MX.getCurrentThreadCpuTime();
    CfCore c = core[i];
    for (int seat = 0; seat < 2; seat++) {
      if (unit(i) < pPlay) {
        int hs = (int) (unit(i) * 4);
        int x = 500 + (int) (unit(i) * 17000), y = 500 + (int) (unit(i) * 31000), cell = (int) (unit(i) * 36 * 64);
        if (c.check(seat, hs) == 0) {
          int deal = c.s.std.getMatch().side(seat).getHand().slots()[hs], tick = c.tick();
          if (c.play(seat, hs, x, y)[0] == 0) {
            plays.incrementAndGet();
            id[i].played(c, seat, tick, inv[deal], cell);
            po[i].act(seat, tick, c.s.deckIds[seat][deal]);
          }
        }
      }
      int nb = c.s.buttons[seat].length;
      if (nb > 0 && unit(i) < pPress) {
        int b = (int) (unit(i) * nb);
        if (c.ability(seat, b, false) == 0) { presses.incrementAndGet(); po[i].press(seat, c.tick(), b); }
      }
    }
    try {
      c.step(decideEvery);
    } catch (RuntimeException e) {                       // crforge refuses a case it does not model: drop that match
      if (crashes.getAndIncrement() == 0) firstCrash = String.valueOf(e);
      reset(i);
      return;                                            // its seats build no row this round
    }
    decisions.incrementAndGet();
    if (c.over()) { matches.incrementAndGet(); ticks.addAndGet(c.tick()); reset(i); }
    long t1 = MX.getCurrentThreadCpuTime();
    if (buildObs)
      for (int seat = 0; seat < 2; seat++) obs(i, seat);
    long t2 = MX.getCurrentThreadCpuTime();
    engineNs.addAndGet(t1 - t0);
    obsNs.addAndGet(t2 - t1);
  }

  /** One seat's row, in e1_eval.Match.prepare's order: the public counter sees the board, then the main tensors (sc[5]
   *  = its estimate at tick + h), opp_past, the identity arrays + past, the public-observer keys. */
  void obs(int i, int seat) {
    CfCore c = core[i];
    CfObsBind.FacadeMatch x = m[i];
    int r = 2 * i + seat;
    CfObsBind.bind(x, c, seat, inv);
    CfOppElixir opp = x.opp(seat, keys);
    if (!opp.update()) missOpp.incrementAndGet();
    x.obs(seat, names, tok, r * MAX_U * F, maskB, r * MAX_U, sc, r * S, formB, r * MAX_U);
    if (cue != null && !CfCue.build(c, seat, cue, cueSeat[i][seat], tok, r * MAX_U * F, maskB, r * MAX_U, cueF, r * CUE))
      missCue.incrementAndGet();
    opp.past(oppPast, r * PAST);
    id[i].build(c, seat, inv, idsL, r * IDS, past, r * PAST);
    if (po[i].update(seat)) po[i].build(seat, proj, r * PROJ, eff, r * EFF, abil, r * ABIL, opp, cyc, r * CYC);
    else missPub.incrementAndGet();
    rows.incrementAndGet();
  }

  public void step() {
    AtomicInteger at = new AtomicInteger();
    List<Callable<Void>> tasks = new ArrayList<>();
    for (int t = 0; t < threads; t++) tasks.add(() -> { for (int i; (i = at.getAndIncrement()) < n; ) stepEnv(i); return null; });
    try {
      for (Future<Void> f : pool.invokeAll(tasks)) f.get();
    } catch (InterruptedException | ExecutionException e) {
      throw new RuntimeException(e);
    }
  }

  public void stepAsync() {
    if (pending != null) throw new IllegalStateException("a step is already running");
    pending = ForkJoinPool.commonPool().submit(this::step);
  }

  public void await_() {
    try { pending.get(); } catch (Exception e) { throw new RuntimeException(e); } finally { pending = null; }
  }

  /** CfOppElixir key names (package-private there) for Python's cyc table. */
  public int detKeys() { return keys.name.size(); }

  @Override public void close() { pool.shutdownNow(); }
}
