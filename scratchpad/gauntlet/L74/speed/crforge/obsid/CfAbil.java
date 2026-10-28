// LOOP-IW (plan1026 fast loop): the hero ability press observation on the facade battle, a port of what
// royale_env.RoyalePoolEnv runs at the live cfg (hero_abilities, ability_policy v2, ROYALE_HEROIW_PRESS live,
// ability_features freeze, heroiw ENABLED; the Python names are in each method's comment):
//   commands(side)  = ability_commands: LiveIWPolicy.observe, the v2 clock, _scan(_v2_gate) -> the rule's presses
//                     (3b: hero Ice Wizard, LiveIWPolicy.gate; 3c: the 24 v2 heroes, _v2_q + the seeded draw; else _near)
//   options(side)   = ability_options: _scan(no gate) -> per button (cmd, q, _ability_head_features + freeze)   (3a)
//   recheck(side)   = _fire_abilities' _scan(_any_gate | _v2_recheck)
// The Python env state those read is kept here from the loop's events: reset (after every CfCore reset), played (an
// accepted play), queue / due (the _ability_pending queue), pressed (an accepted press).
// Floats: the same IEEE operations in production's order; exp / pow are glibc's through JDK 17's incubator FFI (EXACT;
// JVM flags --add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED), else Math.* (not byte-exact).
// The seeded draw random.Random(f"ability:{seed}:{tag}:{side}:{uid}:{tick}").random() is CPython's MT19937 with its
// str seeding (sha512, init_by_array), reproduced bit-exact here. Tables (Tables) are filled from production code by
// ability_id.py; a key not there yet -> the call returns null with the key in Tables.missing (fill, call again: every
// side effect before the miss is the same on the second call at the same tick).

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodType;
import java.lang.reflect.Array;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;
import org.crforge.core.pathfinding.target.TargetView;

public final class CfAbil {
  // ---------------------------------------------------------------------------------------------- libm (glibc via FFI)
  static final MethodHandle EXP, POW;
  public static final boolean EXACT;
  static {
    MethodHandle e = null, p = null;
    try {
      Class<?> cl = Class.forName("jdk.incubator.foreign.CLinker"), ml = Class.forName("jdk.incubator.foreign.MemoryLayout"),
          fd = Class.forName("jdk.incubator.foreign.FunctionDescriptor"), ad = Class.forName("jdk.incubator.foreign.Addressable"),
          sl = Class.forName("jdk.incubator.foreign.SymbolLookup");
      Object linker = cl.getMethod("getInstance").invoke(null), lookup = cl.getMethod("systemLookup").invoke(null);
      Object dbl = cl.getField("C_DOUBLE").get(null);
      Object a1 = Array.newInstance(ml, 1), a2 = Array.newInstance(ml, 2);
      Array.set(a1, 0, dbl); Array.set(a2, 0, dbl); Array.set(a2, 1, dbl);
      var of = fd.getMethod("of", ml, a1.getClass());
      var dh = cl.getMethod("downcallHandle", ad, MethodType.class, fd);
      var lk = sl.getMethod("lookup", String.class);
      e = (MethodHandle) dh.invoke(linker, ((Optional<?>) lk.invoke(lookup, "exp")).get(),
          MethodType.methodType(double.class, double.class), of.invoke(null, dbl, a1));
      p = (MethodHandle) dh.invoke(linker, ((Optional<?>) lk.invoke(lookup, "pow")).get(),
          MethodType.methodType(double.class, double.class, double.class), of.invoke(null, dbl, a2));
    } catch (Throwable t) { e = p = null; }
    EXP = e; POW = p; EXACT = e != null && p != null;
  }
  static double exp(double x) {
    if (!EXACT) return Math.exp(x);
    try { return (double) EXP.invokeExact(x); } catch (Throwable t) { throw new IllegalStateException(t); }
  }
  static double pow(double x, double y) {
    if (!EXACT) return Math.pow(x, y);
    try { return (double) POW.invokeExact(x, y); } catch (Throwable t) { throw new IllegalStateException(t); }
  }
  public static double libmExp(double x) { return exp(x); }
  public static double libmPow(double x, double y) { return pow(x, y); }

  // ---------------------------------------------------------------------------------------------- tables
  /** Shared by every match; ability_id.py fills them from production code. Arrays by RoyaleSim catalogue card id. */
  public static final class Tables {
    public double[] bodyElixir = {}, cardCost = {}, heroRadius = {};    // _body_elixir, _card_cost, _hero_radius (0 none)
    // _hero_ranges[name] for the name _near / _ability_radius look up: a champion troop (debug name = card), a hero
    // troop (card + "_hero"), a non-troop body (_hero_buildings.get(cid, card + "_hero")); NaN = no entry (KeyError)
    public double[] rangeChamp = {}, rangeHero = {}, rangeOther = {};
    public int[] abilityCard = {}, v2Key = {};                          // ABILITY_CARDS index (-1 other), v2 model (-1)
    public boolean[] iceWizard = {}, wincon = {}, tesla = {}, iwSlug = {};   // name IceWizard, WINCONS, live 'Tesla', card_key ice-wizard
    public double[] ownCost = {};                                       // IW model cards.get(card_key(name), [3])[0]
    public int goblins = -1, nCards = 25;                               // ids.get("Goblins"), len(ABILITY_CARDS)
    public CfOppElixir.Keys keys;                                       // the IW observers' detector keys
    // per detector key (keys index): make_play's cards row (cost, kind 0 troop / 1 spell / 2 building, speed), wincon slug
    public double[] keyCost = {}, keySpeed = {};
    public int[] keyKind = {};
    public boolean[] keyWincon = {};
    final HashMap<String, Integer> pubId = new HashMap<>();             // "card|body row|form bits" -> public_frame card id
    final HashMap<Integer, double[]> nat = new HashMap<>();             // public card id -> {unit value, building, wincon}
    public final Set<String> missing = java.util.concurrent.ConcurrentHashMap.newKeySet();
    public void putPub(String k, int nid) { pubId.put(k, nid); }
    public void putNat(int nid, double value, boolean building, boolean wincon) {
      nat.put(nid, new double[] {value, building ? 1 : 0, wincon ? 1 : 0});
    }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }
    // L70 v2 press models (ability_policy.predict_model)
    final ArrayList<Model> models = new ArrayList<>();
    public int addModel(double intercept, double offset, double[] mean, double[] scale, double[] coef, double[] knots,
                        double[] values, double treesScale, double lr, int maxCharges) {
      models.add(new Model(intercept, offset, mean, scale, coef, knots, values, treesScale, lr, maxCharges));
      return models.size() - 1;
    }
    public void addTree(int m, int[] feature, double[] threshold, int[] left, int[] right, double[] value) {
      models.get(m).trees.add(new Object[] {feature, threshold, left, right, value});
    }
    // ability_ice_wizard.frosty_fella_press_probability: model order -> this class's FEATURE index
    public double hzIntercept, hzShift;
    public double[] hzMean = {}, hzScale = {}, hzCoef = {};
    public int[] hzIdx = {};
  }

  static final class Model {
    final double intercept, offset, treesScale, lr;
    final double[] mean, scale, coef, knots, values;
    final int maxCharges;
    final ArrayList<Object[]> trees = new ArrayList<>();
    Model(double intercept, double offset, double[] mean, double[] scale, double[] coef, double[] knots, double[] values,
          double treesScale, double lr, int maxCharges) {
      this.intercept = intercept; this.offset = offset; this.mean = mean; this.scale = scale; this.coef = coef;
      this.knots = knots; this.values = values; this.treesScale = treesScale; this.lr = lr; this.maxCharges = maxCharges;
    }
  }

  static final class Miss extends RuntimeException {
    private static final long serialVersionUID = 1L;
    Miss() { super(null, null, false, false); }
  }
  static final Miss MISS = new Miss();
  static final int K = 18, T = 18000, NONE = Integer.MIN_VALUE, REPRESS = 60, HERO_IW = 203000023;
  static final double[] V2_SCALE = {30., 1., 10., 10., 5., 2000., 5., 2000., 1., 10., 10., 3., 3., 3.};
  static final double[] MY_LINE = {6.5, 25.5};
  static final double[] KNOTS = {0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 11.0, 15.0, 20.0, 30.0};
  static final int[] EIGHTS = {8, 8, 8, 8, 8, 8, 8, 8};

  // ---------------------------------------------------------------------------------------------- per match
  final CfCore core;
  final Tables t;
  public final boolean freeze;
  long seed;
  String tag = "";
  int decisionTicks = 10;
  boolean liveIW = true, iwNever;
  @SuppressWarnings({"unchecked", "rawtypes"}) final HashSet<Integer>[] heroIds = new HashSet[] {new HashSet<>(), new HashSet<>()},
      champ = new HashSet[] {new HashSet<>(), new HashSet<>()};
  final boolean[] hasIW = new boolean[2];
  final HashMap<Long, int[]> info = new HashMap<>();             // _ability_uid: (side, uid) -> {dep, presses, last}
  final HashMap<Long, Integer> lastPlay = new HashMap<>();       // _last_play: (side, cid) -> act tick
  final ArrayList<int[]> pending = new ArrayList<>();            // _ability_pending: {due, side, button, cid, uid}
  @SuppressWarnings({"unchecked", "rawtypes"}) final ArrayList<int[]>[] plays = new ArrayList[] {new ArrayList<>(), new ArrayList<>()};
  final int[][] check = {{NONE, NONE}, {NONE, NONE}};            // _ability_check
  final int[] obsTick = {NONE, NONE};
  double v2dt;
  final CfObsBind.FacadeMatch fm;
  public long nanos, calls;                                      // cost: wall ns inside commands / options / recheck

  public CfAbil(CfCore core, Tables t, boolean freeze) {
    this.core = core; this.t = t; this.freeze = freeze;
    fm = new CfObsBind.FacadeMatch(core.tables);
  }

  static long key(int a, int b) { return (long) a << 32 | (b & 0xffffffffL); }

  /** _reset_abilities after a CfCore reset: env seed + entry tag (the v2 draw), decision_ticks, the IW press mode. */
  public void reset(long seed, String tag, int decisionTicks, boolean liveIW, boolean iwNever) {
    this.seed = seed; this.tag = tag; this.decisionTicks = decisionTicks; this.liveIW = liveIW; this.iwNever = iwNever;
    info.clear(); lastPlay.clear(); pending.clear();
    for (int s = 0; s < 2; s++) {
      plays[s].clear(); check[s][0] = check[s][1] = obsTick[s] = NONE;
      heroIds[s].clear(); champ[s].clear();
      for (int k = 0; k < 8; k++) if (core.s.forms[s][k] == 2) heroIds[s].add(core.s.deckIds[s][k]);
      TowerEntity king = core.s.std.getWorld().kingTower(s);
      for (int b = 0; b < core.s.buttons[s].length; b++) {
        int cid = core.s.deckIds[s][king.championSlot(core.s.buttons[s][b]).getDeckIndex()];
        if (!heroIds[s].contains(cid)) champ[s].add(cid);
      }
      heroIds[s].addAll(champ[s]);
      hasIW[s] = false;
      for (int c : heroIds[s]) hasIW[s] |= c < t.iceWizard.length && t.iceWizard[c];
    }
    CfObsBind.bind(fm, core, 0, EIGHTS);                         // a new battle: the IW observers start again
  }

  /** An accepted play (royale_env _Core.act): _last_play and public_plays (dated at the run, actTick + delay). */
  public void played(int side, int cid, int actTick, int delay) {
    lastPlay.put(key(side, cid), actTick);
    plays[side].add(new int[] {actTick + delay, cid});
  }

  /** queue_abilities: one command (due = tick + delay), unless that side's button is already pending. */
  public void queue(int side, int button, int cid, int uid, int due) {
    for (int[] p : pending) if (p[1] == side && p[2] == button) return;
    pending.add(new int[] {due, side, button, cid, uid});
    pending.sort(Arrays::compare);
  }

  /** _fire_abilities' pops at tick: the due entries in order, flat {due, side, button, cid, uid}. */
  public int[] due(int tick) {
    ArrayList<Integer> out = new ArrayList<>();
    while (!pending.isEmpty() && pending.get(0)[0] <= tick) for (int v : pending.remove(0)) out.add(v);
    return out.stream().mapToInt(Integer::intValue).toArray();
  }

  public int[] pendingFlat() {
    int[] o = new int[pending.size() * 5];
    for (int i = 0; i < pending.size(); i++) System.arraycopy(pending.get(i), 0, o, i * 5, 5);
    return o;
  }

  /** An accepted press: _ability_uid.setdefault(dep = tick), presses + 1, last = tick. */
  public void pressed(int side, int cid, int uid, int tick) {
    int[] in = info.computeIfAbsent(key(side, uid), z -> new int[] {tick, 0, NONE});
    in[1]++;
    in[2] = tick;
  }

  /** (dep, presses, last or MIN) of a (side, uid), or null. */
  public int[] info(int side, int uid) { return info.get(key(side, uid)); }

  // ---------------------------------------------------------------------------------------------- the board
  // the facade's state() entities (alive WorldEntities but the MightyMinerBomb, holder order), the fields read here
  int n;
  int[] id = new int[64], sd = new int[64], kind = new int[64], card = new int[64], hp = new int[64], mhp = new int[64],
      bits = new int[64];
  long[] x = new long[64], y = new long[64];
  boolean[] f16 = new boolean[64];
  WorldEntity[] ent = new WorldEntity[64];
  int tick, elixir;

  void snap() {
    List<BattleEntity> list = core.s.std.getBattle().getHolder().entities();
    if (list.size() > id.length) {
      int c = 2 * list.size();
      id = new int[c]; sd = new int[c]; kind = new int[c]; card = new int[c]; hp = new int[c]; mhp = new int[c];
      bits = new int[c]; x = new long[c]; y = new long[c]; f16 = new boolean[c]; ent = new WorldEntity[c];
    }
    n = 0;
    for (BattleEntity e : list) {
      if (!(e instanceof WorldEntity w) || !w.getView().isAlive() || CfCore.bombAsSpell(w)) continue;
      int i = n++;
      HitPoints h = w.getHitPoints();
      ent[i] = w; id[i] = w.getId(); sd[i] = w.side(); x[i] = (long) w.x() * K; y[i] = (long) w.y() * K;
      hp[i] = h == null ? 0 : h.getHitPoints(); mhp[i] = h == null ? 0 : h.getMaximum();
      card[i] = -1; bits[i] = 0;
      if (w instanceof TowerEntity tw) kind[i] = tw.getData().king() ? 2 : 3;
      else {
        kind[i] = w.getData().building() ? 1 : 0;
        String body = w.getData().name(), root = core.rootCard(w.name());
        Integer p = core.byRoot.get(body + "|" + root);
        if (p == null) p = core.unique.get(body);
        int fl = p == null ? 0 : p & 0xff;
        if (p != null) card[i] = p >> 8;
        if (w instanceof CharacterEntity c && core.heroBody(c)) fl |= 16;
        bits[i] = (fl | CfCore.evolvedBit(w)) & 24;
      }
      f16[i] = (bits[i] & 16) != 0;
    }
    tick = core.tick();
  }

  int elixirMilli(int side) { return core.s.std.getMatch().side(side).getElixir() / 10; }

  /** The IW cube's target rule's second choice: the body hero's acquired target (state()'s target column), or -1. */
  int targetOf(int i) {
    TargetView ref = CfCore.acquired(ent[i]);
    if (ref == null) return -1;
    WorldEntity te = core.s.std.getWorld().entityOf(ref.getEntity());
    return te == null ? -1 : te.getId();
  }

  boolean marked(int i) {
    String idle = ent[i].getData().buffWhenNotAttacking();
    for (BuffInstance bi : ent[i].getBuffs().items()) {
      String nm = bi.getBuff().name();
      if (nm.equals(idle) || !nm.contains("IceWizardHero")) continue;
      for (String part : nm.split("\\|")) if (part.equals("IceWizardHeroCold") || part.equals("IceWizardHeroSlow")) return true;
    }
    return false;
  }

  // ---------------------------------------------------------------------------------------------- _scan
  interface Gate { boolean ok(int side, int button, int cid, int hi); }

  ArrayList<int[]> scan(int side, Gate g) {
    ArrayList<int[]> out = new ArrayList<>();
    TowerEntity king = core.s.std.getWorld().kingTower(side);
    int milli = elixirMilli(side);
    for (int b = 0; b < core.s.buttons[side].length; b++) {
      var slot = king.championSlot(core.s.buttons[side][b]);
      int cid = core.s.deckIds[side][slot.getDeckIndex()];
      if (!heroIds[side].contains(cid) || pendingHas(side, b)) continue;
      if (iwNever && t.iceWizard[cid]) continue;
      int cost = slot.getChampion().ability() == null ? 0 : slot.getChampion().ability().manaCost();   // row[2]
      if (milli < cost * 1000) continue;
      if (core.ability(side, b, true) != 0) continue;              // check_deploy != OK
      int hi = hero(side, cid, champ[side].contains(cid));
      if (hi < 0) continue;
      if (g.ok(side, b, cid, hi)) out.add(new int[] {b, cid, id[hi], hi, cost});
    }
    return out;
  }

  boolean pendingHas(int side, int b) {
    for (int[] p : pending) if (p[1] == side && p[2] == b) return true;
    return false;
  }

  /** A champion is its biggest living body ((max_hp, uid)), a hero its newest (uid); controller_body. */
  int hero(int side, int cid, boolean champion) {
    int best = -1;
    for (int i = 0; i < n; i++) {
      if (sd[i] != side || card[i] != cid || hp[i] <= 0 || !(f16[i] || champion)) continue;
      if (best < 0 || (champion ? mhp[i] > mhp[best] || (mhp[i] == mhp[best] && id[i] > id[best]) : id[i] > id[best])) best = i;
    }
    return best;
  }

  double range(int cid, int hi) {
    return kind[hi] == 0 ? (f16[hi] ? t.rangeHero[cid] : t.rangeChamp[cid]) : t.rangeOther[cid];
  }

  /** _near: any enemy within the hero's attack range + 1.5 tiles. */
  boolean near(int side, int cid, int hi) {
    double r = range(cid, hi);
    if (Double.isNaN(r)) throw new IllegalStateException("_hero_ranges has no entry for card " + cid + " (KeyError)");
    long reach = (long) r + 1500 * K;
    for (int i = 0; i < n; i++) {
      if (sd[i] != 1 - side || hp[i] <= 0) continue;
      long dx = x[i] - x[hi], dy = y[i] - y[hi];
      if (dx * dx + dy * dy <= reach * reach) return true;
    }
    return false;
  }

  double radius(int cid, int hi) {
    double r = cid < t.heroRadius.length ? t.heroRadius[cid] : 0;
    if (r != 0) return r;
    double g = range(cid, hi);
    return (Double.isNaN(g) ? 0 : g) + 1500 * K;
  }

  int[] v2info(int side, int cid, int hi) {
    return info.computeIfAbsent(key(side, id[hi]), z -> new int[] {lastPlay.getOrDefault(key(side, cid), tick), 0, NONE});
  }

  // ---------------------------------------------------------------------------------------------- public calls
  /** ability_commands(side): flat {button, cid, uid}*, or null (Tables.missing / keys.missing: fill, call again). */
  public int[] commands(int side) {
    long t0 = System.nanoTime();
    try {
      snap();
      if (liveIW && hasIW[side]) observe(side);
      if (heroIds[side].isEmpty()) return new int[0];
      int[] last = check[side];
      if (last[1] != tick) { last[0] = last[1]; last[1] = tick; }
      v2dt = (last[0] == NONE ? decisionTicks : tick - last[0]) / 20.0;
      return flat(scan(side, this::v2gate), 3);
    } catch (Miss m) {
      return null;
    } finally { nanos += System.nanoTime() - t0; calls++; }
  }

  /** ability_options(side, rule): per option {button, cid, uid, q (NaN = no rule), feat...}; rule = the flat commands
   *  ability_commands just gave this side (label mode), or null. */
  public double[] options(int side, int[] rule) {
    long t0 = System.nanoTime();
    try {
      snap();
      if (heroIds[side].isEmpty()) return new double[0];
      int nf = 44 + (freeze ? 11 : 0);
      ArrayList<double[]> rows = new ArrayList<>();
      scan(side, (s, b, cid, hi) -> {
        double[] r = new double[4 + nf];
        r[0] = b; r[1] = cid; r[2] = id[hi]; r[3] = Double.NaN;
        headFeat(s, b, cid, hi, r, 4);
        if (rule != null) {
          double q = t.iceWizard[cid] && liveIW ? Double.NaN : v2q(cid, hi);
          if (Double.isNaN(q)) {
            q = 0.0;
            for (int k = 0; k + 2 < rule.length; k += 3) if (rule[k] == b && rule[k + 1] == cid && rule[k + 2] == id[hi]) q = 1.0;
          }
          r[3] = q;
        }
        rows.add(r);
        return false;
      });
      double[] o = new double[rows.size() * (4 + nf)];
      for (int i = 0; i < rows.size(); i++) System.arraycopy(rows.get(i), 0, o, i * (4 + nf), 4 + nf);
      return o;
    } catch (Miss m) {
      return null;
    } finally { nanos += System.nanoTime() - t0; calls++; }
  }

  /** _fire_abilities' recheck: _scan(_any_gate) for a learned side, else _scan(_v2_recheck). Flat {button, cid, uid}*. */
  public int[] recheck(int side, boolean learned) {
    long t0 = System.nanoTime();
    try {
      snap();
      return flat(scan(side, (s, b, cid, hi) -> learned || (t.iceWizard[cid] && liveIW) || t.v2Key[cid] >= 0
          || near(s, cid, hi)), 3);
    } finally { nanos += System.nanoTime() - t0; calls++; }
  }

  static int[] flat(ArrayList<int[]> l, int w) {
    int[] o = new int[l.size() * w];
    for (int i = 0; i < l.size(); i++) System.arraycopy(l.get(i), 0, o, i * w, w);
    return o;
  }

  // ---------------------------------------------------------------------------------------------- 3c: the v2 rule
  public long nIw, nV2, nNear, nHazard;                          // diagnostics: which rule decided

  boolean v2gate(int side, int b, int cid, int hi) {
    if (t.iceWizard[cid] && liveIW) { nIw++; return iwGate(side, cid, hi); }
    double q = v2q(cid, hi);
    if (Double.isNaN(q)) { nNear++; return near(side, cid, hi); }
    nV2++;
    return q > 0 && draw("ability:" + seed + ":" + tag + ":" + side + ":" + id[hi] + ":" + tick) < q;   // r >= 0: q 0 never presses
  }

  /** _v2_q: 1 - (1 - p)^dt, 0 once the deployment's presses are used, NaN for a card without a v2 model. */
  double v2q(int cid, int hi) {
    int mi = t.v2Key[cid];
    if (mi < 0) return Double.NaN;
    Model m = t.models.get(mi);
    int side = sd[hi];
    int[] in = v2info(side, cid, hi);
    int presses = in[1];
    if (presses >= m.maxCharges || (presses != 0 && tick - in[2] < REPRESS)) return 0.0;
    double p = predict(m, feat14(side, hi, in[0]), presses);
    return 1 - pow(1 - p, v2dt);
  }

  /** ability_policy.predict_model (logistic_timing / gbt_timing), one row. */
  static double predict(Model m, double[] x, int charge) {
    for (double v : x) if (!Double.isFinite(v)) throw new IllegalArgumentException("Expected finite values");
    double score = m.intercept + (charge != 0 ? m.offset : 0.);
    double[] z = new double[14];
    for (int i = 0; i < 14; i++) z[i] = (x[i] - m.mean[i]) / m.scale[i];
    if (m.trees.isEmpty()) {
      double d = 0.0;
      for (int i = 0; i < 14; i++) d += z[i] * m.coef[i];        // numpy's 14-term dot: sequential, no FMA (fp/ probe)
      score += d;
    } else {
      double s = 0;                                              // Python sum(): 0 + each tree in order
      for (Object[] tr : m.trees) s += m.lr * leaf(tr, z);
      score += m.treesScale * s;
    }
    score += interp(x[0], m.knots, m.values);
    double c = Math.min(Math.max(score, -40), 40);
    return 1 / (1 + exp(-c));
  }

  static double leaf(Object[] tr, double[] z) {
    int[] f = (int[]) tr[0], l = (int[]) tr[2], r = (int[]) tr[3];
    double[] th = (double[]) tr[1], v = (double[]) tr[4];
    int i = 0;
    while (f[i] >= 0) i = z[f[i]] <= th[i] ? l[i] : r[i];
    return v[i];
  }

  /** numpy arr_interp for one value (binary_search_with_guess: the largest j with xp[j] <= x). */
  static double interp(double x, double[] xp, double[] fp) {
    int len = xp.length;
    if (Double.isNaN(x)) return x;
    if (x > xp[len - 1]) return fp[len - 1];
    if (x < xp[0]) return fp[0];
    int j = 0;
    while (j + 1 < len && x >= xp[j + 1]) j++;
    if (j == len - 1 || xp[j] == x) return fp[j];
    double slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    double r = slope * (x - xp[j]) + fp[j];
    if (Double.isNaN(r)) {
      r = slope * (x - xp[j + 1]) + fp[j + 1];
      if (Double.isNaN(r) && fp[j] == fp[j + 1]) r = fp[j];
    }
    return r;
  }

  /** _ability_features: the 14 L70 features (ints as doubles). Distances: d = pow(n, .5) / 18000 with n = dx^2 + dy^2
   *  (exact integers); d is monotone in n and d <= 3 / 5 iff n <= 54000^2 / 90000^2 (neighbouring integers' roots
   *  differ by >> 1 ulp), so only the minimum n of each group is taken through pow. */
  double[] feat14(int side, int hi, int dep) {
    long nu = Long.MAX_VALUE, ns = Long.MAX_VALUE, nt = Long.MAX_VALUE, h3 = 0, h5 = 0;
    int c3 = 0, c5 = 0;
    for (int i = 0; i < n; i++) {
      if (sd[i] == side || hp[i] <= 0) continue;
      long dx = x[i] - x[hi], dy = y[i] - y[hi], q = dx * dx + dy * dy;
      if (kind[i] >= 2) { nt = Math.min(nt, q); ns = Math.min(ns, q); }
      else if (card[i] == -1) continue;
      else if (kind[i] == 1) { if (!(card[i] == t.goblins && f16[i])) ns = Math.min(ns, q); }
      else {
        nu = Math.min(nu, q);
        if (q <= 2_916_000_000L) { c3++; h3 += hp[i]; }
        if (q <= 8_100_000_000L) { c5++; h5 += hp[i]; }
      }
    }
    var match = core.s.std.getMatch();
    double hpf = (double) hp[hi] / Math.max(1, mhp[hi]);
    return new double[] {(tick - dep) / 20.0, Math.min(1., Math.max(0., hpf)), dist(nu), dist(ns), c3, h3, c5, h5,
        (side == 0 ? y[hi] > 16L * T : y[hi] < 16L * T) ? 1.0 : 0.0, dist(nt), elixirMilli(side) / 1000.0,
        Math.min(Math.floorDiv(tick, 1200), 3), tick < 2400 ? 1 : tick < 4800 ? 2 : 3,
        match.crowns(side) - match.crowns(1 - side)};
  }

  static double dist(long q) { return q == Long.MAX_VALUE ? 40. : pow((double) q, .5) / T; }

  // ---------------------------------------------------------------------------------------------- 3a: the head inputs
  /** _ability_head_features (+ _freeze_features when freeze) into r[o ..]. */
  void headFeat(int side, int b, int cid, int hi, double[] r, int o) {
    int[] in = v2info(side, cid, hi);
    double[] f = feat14(side, hi, in[0]);
    for (int i = 0; i < 14; i++) r[o + i] = f[i] / V2_SCALE[i];
    double rad = radius(cid, hi), r2 = rad * rad;
    int cnt = 0, tower = 0;
    double el = 0;
    for (int i = 0; i < n; i++) {
      if (sd[i] == side || hp[i] <= 0) continue;
      long dx = x[i] - x[hi], dy = y[i] - y[hi];
      if ((double) (dx * dx + dy * dy) > r2) continue;
      if (kind[i] >= 2) tower = 1;
      else if (card[i] != -1) { cnt++; el += card[i] < t.bodyElixir.length ? t.bodyElixir[card[i]] : 0.; }
    }
    r[o + 14] = cnt / 5.0; r[o + 15] = el / 10; r[o + 16] = tower; r[o + 17] = in[1];
    for (int k = 0; k <= t.nCards; k++) r[o + 18 + k] = 0;
    int ac = t.abilityCard[cid];
    r[o + 18 + (ac >= 0 ? ac : t.nCards)] = 1;
    if (freeze) freezeFeat(side, b, cid, hi, r, o + 18 + t.nCards + 1);
  }

  /** _freeze_features (11, zeros unless Hero Ice Wizard). */
  void freezeFeat(int side, int b, int cid, int hi, double[] r, int o) {
    Arrays.fill(r, o, o + 11, 0.);
    if (!t.iceWizard[cid]) return;
    int tg = -1;
    long best = 0;
    boolean anyMarked = false;
    for (int i = 0; i < n; i++) {
      if (!foe(i, side) || !marked(i)) continue;
      anyMarked = true;
      long dx = x[i] - x[hi], dy = y[i] - y[hi], q = dx * dx + dy * dy;
      if (tg < 0 || q < best) { tg = i; best = q; }
    }
    if (tg < 0) {
      int tu = targetOf(hi);
      for (int i = 0; i < n && tu != -1; i++) if (id[i] == tu && sd[i] != side && hp[i] > 0) { tg = i; break; }
    }
    var me = core.s.std.getMatch().side(side);
    int[] h = me.getHand().slots();
    double cheap = 0.;
    boolean first = true;
    for (int k = 0; k < 4; k++) {
      int c = h[k] >= 0 ? core.s.deckIds[side][h[k]] : -1;
      if (c == -1) continue;
      double v = c < t.cardCost.length ? t.cardCost[c] : 0.;
      if (first || v < cheap) { cheap = v; first = false; }
    }
    var slot = core.s.std.getWorld().kingTower(side).championSlot(core.s.buttons[side][b]);
    double cost = slot.getChampion().ability() == null ? 0 : slot.getChampion().ability().manaCost();
    r[o + 9] = anyMarked ? 1. : 0.;
    r[o + 10] = (elixirMilli(side) / 1000.0 - cost - cheap) / 10;
    if (tg < 0) return;
    double cy = y[tg] + (side == 0 ? 1 : -1) * 1.5 * T;
    r[o] = 1.;
    around(side, x[tg], y[tg], r, o + 1);
    around(side, x[tg], cy, r, o + 4);
    r[o + 7] = Math.abs(cy / T - MY_LINE[side]) / 10;
    r[o + 8] = (cy > 16 * T) == (side == 1) ? 1. : 0.;
  }

  boolean foe(int i, int side) { return sd[i] != side && hp[i] > 0 && card[i] != -1 && kind[i] == 0; }

  void around(int side, double px, double py, double[] r, int o) {
    int cnt = 0;
    double el = 0;
    boolean w = false;
    for (int i = 0; i < n; i++) {
      if (!foe(i, side)) continue;
      double dx = x[i] - px, dy = y[i] - py;
      if (dx * dx + dy * dy > 2.025e9) continue;                    // (2.5 * 18000) ** 2
      cnt++;
      el += card[i] < t.bodyElixir.length ? t.bodyElixir[card[i]] : 0.;
      w |= card[i] < t.wincon.length && t.wincon[card[i]];
    }
    r[o] = cnt / 5.0; r[o + 1] = el / 10; r[o + 2] = w ? 1. : 0.;
  }

  // ---------------------------------------------------------------------------------------------- 3b: the IW live rule
  /** LiveIWPolicy.observe: the side's own PublicObserver (CfOppElixir) fed at every commands(side) (once per tick). */
  void observe(int side) {
    if (obsTick[side] == tick) return;
    CfOppElixir o = fm.opp(side, t.keys);
    if (!o.update()) throw MISS;
    obsTick[side] = tick;
  }

  /** public_frame(source 'sim') card id of entity i (raw() drops towers and card -1 first), -1 = dropped. */
  int pub(int i) {
    String k = card[i] + "|" + ent[i].getData().name() + "|" + bits[i];
    Integer v = t.pubId.get(k);
    if (v == null) { t.missing.add("P:" + k); throw MISS; }
    return v;
  }

  double[] nat(int nid) {
    double[] v = t.nat.get(nid);
    if (v == null) { t.missing.add("N:" + nid); throw MISS; }
    return v;
  }

  /** LiveIWPolicy.gate: dedupe_hero_bodies(public_frame(raw)) -> geometry; then should_press_pro on the last IW deploy. */
  boolean iwGate(int side, int cid, int hi) {
    int[] fr = new int[n], nid = new int[n];
    int m = 0;
    for (int i = 0; i < n; i++) {
      if (kind[i] >= 2 || card[i] == -1 || sd[i] < 0 || sd[i] > 1) continue;
      int c = pub(i);
      if (c < 0 || (hp[i] <= 0 && mhp[i] > 0)) continue;
      fr[m] = i; nid[m++] = c;
    }
    boolean[] drop = new boolean[m];                               // a later 203000023 within 0.5 tile of a kept one
    for (int a = 0; a < m; a++) {
      if (nid[a] != HERO_IW) continue;
      for (int k = 0; k < a && !drop[a]; k++)
        if (nid[k] == HERO_IW && !drop[k] && sd[fr[k]] == sd[fr[a]] && Math.abs(x[fr[k]] - x[fr[a]]) <= 500L * K
            && Math.abs(y[fr[k]] - y[fr[a]]) <= 500L * K) drop[a] = true;
    }
    int vis = -1;
    for (int a = 0; a < m && vis < 0; a++) if (!drop[a] && sd[fr[a]] == side && id[fr[a]] == id[hi]) vis = a;
    boolean ok = geometry(side, fr, nid, drop, m, vis);
    int dep = NONE;
    for (int[] p : plays[side]) if (t.iwSlug[p[1]]) dep = p[0];
    if (dep == NONE) return ok;
    if (!ok) return false;                                         // p >= P* and geometry_ok
    int grid = dep + 20 * Math.floorDiv(tick - dep, 20);
    nHazard++;
    return hazard(side, grid, dep) >= 0.03;
  }

  /** royale_iw_policy.geometry in crforge units (raw x = engine x / 18): distances by exact integer n = dx^2 + dy^2
   *  (d <= 5.5 / 2.5 tiles iff n <= 5500^2 / 2500^2; the nearest target = the first minimum n). */
  boolean geometry(int side, int[] fr, int[] nid, boolean[] drop, int m, int vis) {
    if (vis < 0) return false;
    int hv = fr[vis], tg = -1;
    long best = 0;
    for (int a = 0; a < m; a++) {
      int i = fr[a];
      if (drop[a] || sd[i] == side) continue;
      long dx = (x[i] - x[hv]) / K, dy = (y[i] - y[hv]) / K, q = dx * dx + dy * dy;
      if (q <= 30_250_000L && (tg < 0 || q < best)) { tg = a; best = q; }
    }
    if (tg < 0) return false;
    int ti = fr[tg], cnt = 0;
    double value = 0;
    boolean win = false;
    for (int a = 0; a < m; a++) {
      int i = fr[a];
      if (drop[a] || sd[i] == side) continue;
      long dx = (x[i] - x[ti]) / K, dy = (y[i] - y[ti]) / K;
      if (dx * dx + dy * dy > 6_250_000L) continue;
      double[] nv = nat(nid[a]);
      if (nv[1] != 0) continue;                                    // BUILDINGS
      cnt++;
      value += nv[0];
      win |= nv[2] != 0 && (y[i] / K > 16000) == (side == 1);
    }
    if (cnt >= 2 && value >= 4.0) return true;
    int[] h = core.s.std.getMatch().side(side).getHand().slots();
    boolean tesla = false;
    for (int k = 0; k < 4; k++) if (h[k] >= 0 && t.tesla[core.s.deckIds[side][h[k]]]) tesla = true;
    boolean teslaOk = tesla && elixirMilli(side) * 10 / 1e4 >= 4.0;
    return win && !teslaOk;
  }

  /** ability_ice_wizard.should_press_pro's p: live_features at the grid tick -> frosty_fella_press_probability. */
  double hazard(int side, int now, int dep) {
    CfOppElixir o = fm.opp[side];
    boolean up = side == 1;
    double ts = now * 0.05;
    double[] f = new double[29];
    // opponent plays (make_play): t, cost, kind, mine, wincon
    int no = o.n;
    double[] ot = new double[no], oc = new double[no];
    int[] ok = new int[no];
    boolean[] om = new boolean[no], ow = new boolean[no], use = new boolean[no];
    for (int i = 0; i < no; i++) {
      if (o.ticks[i] > now) continue;
      int k = o.pkey[i];
      if (k >= t.keyCost.length) { t.missing.add("K:" + k); throw MISS; }
      use[i] = true;
      double yy = o.py[i];
      if (t.keyKind[k] == 0) {
        double age = Math.min(12.0, Math.max(0.0, (now - o.ticks[i]) / 20.0 - 1.0));
        yy = Math.min(32000.0, Math.max(0.0, yy + (up ? 1 : -1) * t.keySpeed[k] * 1000.0 * age));
      }
      ot[i] = o.ticks[i] / 20.0; oc[i] = t.keyCost[k]; ok[i] = t.keyKind[k]; om[i] = (yy > 16000) == up; ow[i] = t.keyWincon[k];
    }
    double[] s = new double[12];   // n3 cost3 n6 cost6 troop6 spell6 bld6 mine6 theirs6 mine10
    double since = 20.0;
    boolean sinceSet = false, wm10 = false;
    for (int i = 0; i < no; i++) {
      if (!use[i]) continue;
      double d = ts - ot[i];
      if (0.0 <= d && d <= 3) { s[0]++; s[1] += oc[i]; }
      if (0.0 <= d && d <= 6) {
        s[2]++; s[3] += oc[i];
        if (ok[i] == 0) s[4] += oc[i];
        if (ok[i] == 1) s[5] += oc[i];
        if (ok[i] == 2) s[6] += oc[i];
        if (om[i]) s[7] += oc[i]; else s[8] += oc[i];
      }
      if (0.0 <= d && d <= 10) { if (om[i]) s[9] += oc[i]; wm10 |= om[i] && ow[i]; }
      if (om[i] && 0.0 <= d && d <= 20 && (!sinceSet || d < since)) { since = d; sinceSet = true; }
    }
    double own3 = 0, own6 = 0, ownCost6 = 0;
    for (int[] p : plays[side]) {
      if (t.iwSlug[p[1]] || p[0] > now) continue;
      double d = ts - p[0] * 0.05;
      if (0.0 <= d && d <= 3) own3++;
      if (0.0 <= d && d <= 6) { own6++; ownCost6 += t.ownCost[p[1]]; }
    }
    f[0] = ts / 60.0; f[1] = ts >= 180 ? 1.0 : 0.0; f[2] = elixirMilli(side) * 10 / 1e4; f[3] = o.estimateAt(now);
    for (int k = 0; k < 10; k++) f[4 + k] = s[k];
    f[14] = since; f[15] = wm10 ? 1.0 : 0.0; f[16] = own3; f[17] = own6; f[18] = ownCost6;
    double a = Math.min(Math.max((now - dep) * 0.05, KNOTS[0]), KNOTS[KNOTS.length - 1]);
    for (int j = 1; j < KNOTS.length; j++) {
      double lo = KNOTS[j - 1], mid = KNOTS[j];
      double v;
      if (a < lo) v = 0.0;
      else if (a <= mid) v = (a - lo) / (mid - lo);
      else if (j + 1 >= KNOTS.length) v = 1.0;
      else v = Math.max(0.0, (KNOTS[j + 1] - a) / (KNOTS[j + 1] - mid));
      f[18 + j] = v;
    }
    double z = t.hzIntercept;
    for (int j = 0; j < t.hzIdx.length; j++) z += t.hzCoef[j] * (f[t.hzIdx[j]] - t.hzMean[j]) / t.hzScale[j];
    z = z + t.hzShift;
    z = z < 40.0 ? z : 40.0;                                     // Python min(40.0, z)
    z = z > -40.0 ? z : -40.0;                                   // max(-40.0, z)
    return 1.0 / (1.0 + exp(-z));
  }

  // ---------------------------------------------------------------------------------------------- CPython random
  /** random.Random(s).random() for a str seed (version 2: int.from_bytes(s + sha512(s)) -> init_by_array). */
  public static double draw(String s) {
    byte[] a = s.getBytes(StandardCharsets.UTF_8), dig;
    try { dig = MessageDigest.getInstance("SHA-512").digest(a); } catch (Exception e) { throw new IllegalStateException(e); }
    byte[] b = new byte[a.length + dig.length];
    System.arraycopy(a, 0, b, 0, a.length);
    System.arraycopy(dig, 0, b, a.length, dig.length);
    int st = 0;
    while (st < b.length && b[st] == 0) st++;                    // the int's significant bytes (big endian)
    int nb = b.length - st, kl = Math.max(1, (nb + 3) / 4);
    int[] key = new int[kl];
    for (int i = 0; i < nb; i++) {                               // little-endian 32-bit words from the low end
      int byteFromLow = i, v = b[b.length - 1 - i] & 0xff;
      key[byteFromLow >> 2] |= v << (8 * (byteFromLow & 3));
    }
    int[] mt = new int[624];
    mt[0] = 19650218;
    for (int i = 1; i < 624; i++) mt[i] = 1812433253 * (mt[i - 1] ^ (mt[i - 1] >>> 30)) + i;
    int i = 1, j = 0;
    for (int k = Math.max(624, kl); k > 0; k--) {
      mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >>> 30)) * 1664525)) + key[j] + j;
      i++; j++;
      if (i >= 624) { mt[0] = mt[623]; i = 1; }
      if (j >= kl) j = 0;
    }
    for (int k = 623; k > 0; k--) {
      mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >>> 30)) * 1566083941)) - i;
      i++;
      if (i >= 624) { mt[0] = mt[623]; i = 1; }
    }
    mt[0] = 0x80000000;
    long w0 = temper(twist(mt, 0)) >>> 5, w1 = temper(twist(mt, 1)) >>> 6;   // the first two words after the twist
    return (w0 * 67108864.0 + w1) * (1.0 / 9007199254740992.0);
  }

  static int twist(int[] mt, int kk) {                           // genrand's mt[kk] for kk < 624 - 397 (old values only)
    int yv = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
    return mt[kk + 397] ^ (yv >>> 1) ^ ((yv & 1) != 0 ? 0x9908b0df : 0);
  }

  static long temper(int yv) {
    yv ^= yv >>> 11;
    yv ^= (yv << 7) & 0x9d2c5680;
    yv ^= (yv << 15) & 0xefc60000;
    yv ^= yv >>> 18;
    return yv & 0xffffffffL;
  }
}
