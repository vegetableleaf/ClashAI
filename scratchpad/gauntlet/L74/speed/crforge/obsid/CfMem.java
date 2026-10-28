// LOOP-MEM (plan1026 pilot, LOOP_SPEC.md): production's match memory v2 on the facade battle, for one seat. A port of
// pipeline/match_memory.py (MatchMemory.observe / _sample / _add / the outcomes / events / encode / summary / _s1c /
// table) as pipeline/e1_eval.Match._memory feeds it, once per decision of the seat:
//   sample = sample_sim(Match.state, seat): the UN-extrapolated board at the decision tick: tower_reads_engine on raw()'s
//            crown towers, my elixir_exact, public_frame(source 'sim')'s bodies of BOTH sides (key = vocab.engine_key of
//            catalog_card_form(public card id)[0], Tables.body filled from Python on first sight);
//   plays  = PublicObserver.plays (the opponent's DETECTED plays: the seat's CfOppElixir arrays, read, not re-detected)
//            + own_events (env.public_plays: act tick + 20, card, form, x, y; own_ability_events: press tick, card) of
//            the seat's side, from Log (the loop's own action log).
// Out: features() = the model's MEM_KEYS row at the decision tick (version 'v2') into a ByteBuffer (layout OFF_*);
// table() = the per-match event table (match_memory.TABLE_KEYS = rl_royale's mem_tab_*) at the end of the match.
// Reads no hand, deck or opponent elixir (my own elixir only, as production's sample does).
//
// Exactness notes: Python's sum() of floats (CPython >= 3.12: Neumaier compensated) = pySum; math.hypot = pyHypot
// (CPython's vector_norm); numpy cumsum = sequential; np.round(x, 1) = rint(x * 10) / 10.

import java.nio.ByteBuffer;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfMem {
  // ---------------------------------------------------------------- constants (obs_id.py asserts each against production)
  public static final int W_OUT = 200, DMG_GAP = 20, XB_ANSWER_T = 80, RK_WIN = 100, E_MAX = 128, DECK_N = 8,
      DOUBLE_T = 2400, OT_T = 3600, XB_WINDOW = 600, CYCLE = 4, SLOT_N = 8, FORM_PAD = 3, S = 54, S_V2 = 114, N_S1C = 60,
      N_LOCK = 77, COMBO_LO = -24, COMBO_HI = 40, DELAY = 20, NEVER = Integer.MAX_VALUE;
  public static final double VALUE_R = 5.0, DMG_MIN = 0.02, XB_ANSWER_R = 12.0, RK_R = 2.0, RK_TOWER_R = 3.0,
      XB_REACH = 13.5, XB_LOCK = 0.05, TICK_S = 0.05, COUNTER_LIFT = -0.10, CHILD_VALUE = 1.0 / 3, TILES_X = 18.0,
      TILES_Y = 32.0;
  static final double KX = 9.0 / 18.0, PXL = 3.5 / 18.0, PXR = 1.0 - PXL;
  public static final double[][] TOWER_XY = {{KX, 1.0 - 3.0 / 32.0}, {PXL, 1.0 - 6.5 / 32.0}, {PXR, 1.0 - 6.5 / 32.0},
      {KX, 3.0 / 32.0}, {PXL, 6.5 / 32.0}, {PXR, 6.5 / 32.0}};
  public static final String[] FIELDS = {"is_play", "is_ability", "is_tower_damage", "is_tower_fall", "mine", "x", "y",
      "xy_known", "ago_60", "t_300", "ph_1x", "ph_2x", "ph_ot", "elixir_10", "elixir_known", "crowns_me_3", "crowns_opp_3",
      "margin_2", "margin_known", "cost_10", "tower_k", "tower_l", "tower_r", "tower_lost", "out_done", "out_enemy_lost",
      "out_own_lost", "out_tower_known", "out_value_10", "out_value_known", "xb_reach", "xb_done", "xb_locked",
      "xb_failed", "xb_damage", "xb_answer_done", "xb_answered", "xb_answer_dist_12", "is_xb_answer", "rk_tower",
      "rk_done", "rk_tower_lost", "rk_tower_known", "rk_value_10", "rk_value_known", "rk_combo"};
  static final int PLAY = 0, ABILITY = 1, TDMG = 2, TFALL = 3, MINE = 4, X = 5, Y = 6, XYK = 7, AGO = 8, T300 = 9, PH1 = 10,
      EL10 = 13, ELK = 14, CRM = 15, CRO = 16, MG2 = 17, MGK = 18, COST10 = 19, TK = 20, TLOST = 23, OUT_DONE = 24,
      OUT_EN = 25, OUT_OWN = 26, OUT_TK = 27, OUT_V10 = 28, OUT_VK = 29, XB_REACH_F = 30, XB_DONE = 31, XB_LOCKED = 32,
      XB_FAILED = 33, XB_DMG = 34, XB_ANS_DONE = 35, XB_ANSWERED = 36, XB_ANS_DIST = 37, IS_XB_ANS = 38, RK_TOWER = 39,
      RK_DONE = 40, RK_TLOST = 41, RK_TK = 42, RK_V10 = 43, RK_VK = 44, RK_COMBO = 45;
  public static final int F = 46;
  /** features() row layout (bytes, native order set by the caller): mem_ev f32 [128, 46], mem_mask u8 [128] (bool),
   *  mem_card i64 [128], mem_form i64 [128], mem_summary f32 [114], mem_answer i64. */
  public static final int OFF_EV = 0, OFF_MASK = E_MAX * F * 4, OFF_CARD = OFF_MASK + E_MAX, OFF_FORM = OFF_CARD + 8 * E_MAX,
      OFF_SUM = OFF_FORM + 8 * E_MAX, OFF_ANS = OFF_SUM + 4 * S_V2, BYTES = OFF_ANS + 8;
  static final int PENDING = 0, NONE_ANS = 1, FOUND = 2;

  // ---------------------------------------------------------------- tables (shared; obs_id.py fills them from production)
  public static final class Tables {
    final ArrayList<String> slug = new ArrayList<>();
    final HashMap<String, Integer> slugIdx = new HashMap<>();
    int[] sGid = new int[0];
    double[] sCost = new double[0], sAbCost = new double[0];      // play_cost(slug); ABILITY_COST.get(slug, 0.0)
    int xbow = -2, rocket = -2, tornado = -2;
    public int[] cidSlug = new int[0];    // RoyaleSim card id + 2 -> slug (card_key(env.names[cid])), -1 = none
    public int[] detSlug = new int[0];    // CfOppElixir detector key -> slug (card_key(key)), -1 = none
    final HashMap<String, Integer> body = new HashMap<>();        // "card|body row|form" -> unit key, -1 = not a body here
    public final Set<String> missing = java.util.concurrent.ConcurrentHashMap.newKeySet();   // "card|body|form#entity id"
    // unit keys: habit_terms._card(key) facts for match_memory._value (body_value + the building rule)
    int nU;
    int[] uTop = new int[0];              // unit key of _card(key)[0] (top's lookup key)
    boolean[] uNoBody = new boolean[0], uSpellChild = new boolean[0], uBld = new boolean[0];
    double[] uBase = new double[0], uBldCost = new double[0];
    // v2
    public double[] lutDeck = new double[0], lutAns = new double[0];   // v2_lut(gid) by gid id
    public double[] lockMean, lockStd, lockW;
    public double lockB;
    public double[] regenBp, regenRate, regenCum;                     // match_memory._regen_table()

    public synchronized int addSlug(String s, int gid, double playCost, double abilityCost) {
      Integer i = slugIdx.get(s);
      if (i != null) return i;
      int n = slug.size();
      slug.add(s); slugIdx.put(s, n);
      sGid = Arrays.copyOf(sGid, n + 1); sCost = Arrays.copyOf(sCost, n + 1); sAbCost = Arrays.copyOf(sAbCost, n + 1);
      sGid[n] = gid; sCost[n] = playCost; sAbCost[n] = abilityCost;
      if (s.equals("x-bow")) xbow = n;
      if (s.equals("rocket")) rocket = n;
      if (s.equals("tornado")) tornado = n;
      return n;
    }

    public synchronized int addUnit(boolean noBody, boolean spellChild, double base, boolean bld, double bldCost) {
      int n = nU++;
      uTop = Arrays.copyOf(uTop, nU); uNoBody = Arrays.copyOf(uNoBody, nU); uSpellChild = Arrays.copyOf(uSpellChild, nU);
      uBld = Arrays.copyOf(uBld, nU); uBase = Arrays.copyOf(uBase, nU); uBldCost = Arrays.copyOf(uBldCost, nU);
      uTop[n] = n; uNoBody[n] = noBody; uSpellChild[n] = spellChild; uBase[n] = base; uBld[n] = bld; uBldCost[n] = bldCost;
      return n;
    }

    public synchronized void putTop(int unit, int top) { uTop[unit] = top; }
    public synchronized void putBody(String k, int unit) { body.put(k, unit); }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }
    public int slugs() { return slug.size(); }

    /** match_memory._regen_cum(x) for one x. */
    double regenCum(double x) {
      int i = 0;
      while (i + 1 < regenBp.length && regenBp[i + 1] <= x) i++;    // searchsorted(bp, x, 'right') - 1, at least 0
      return regenCum[i] + regenRate[i] * (x - regenBp[i]);
    }
  }

  // ---------------------------------------------------------------- the loop's own action log (per facade core)
  /** env.public_plays (tick = act tick + DELAY, card, form, x, y) and own_ability_events (press tick, card) per side,
   *  restarted on a new battle. The loop calls play() for every ACCEPTED play (form = playForm read BEFORE the play
   *  was given) and press() for every accepted press. */
  public static final class Log {
    final CfCore core;
    final Tables t;
    Object std;
    final int[][] pTick = new int[2][64], pSlug = new int[2][64], pForm = new int[2][64], pX = new int[2][64],
        pY = new int[2][64], aTick = new int[2][16], aSlug = new int[2][16];
    final int[] pn = new int[2], an = new int[2];

    public Log(CfCore core, Tables t) { this.core = core; this.t = t; }

    void sync() {
      if (core.s.std == std) return;
      std = core.s.std;
      pn[0] = pn[1] = an[0] = an[1] = 0;
    }

    public void play(int side, int actTick, int cid, int form, int x, int y) {
      sync();
      int n = pn[side];
      if (n == pTick[side].length) {
        pTick[side] = Arrays.copyOf(pTick[side], 2 * n); pSlug[side] = Arrays.copyOf(pSlug[side], 2 * n);
        pForm[side] = Arrays.copyOf(pForm[side], 2 * n); pX[side] = Arrays.copyOf(pX[side], 2 * n);
        pY[side] = Arrays.copyOf(pY[side], 2 * n);
      }
      pTick[side][n] = actTick + DELAY; pSlug[side][n] = t.cidSlug[cid + 2]; pForm[side][n] = form;
      pX[side][n] = x; pY[side][n] = y;
      pn[side]++;
    }

    /** An accepted press of RoyaleSim ability button {@code button} at {@code tick}: the card = that button's champion
     *  slot's deck card (as CfPubObj.press and the facade's abilities row). */
    public void press(int side, int tick, int button) {
      sync();
      var slot = core.s.std.getWorld().kingTower(side).championSlot(core.s.buttons[side][button]);
      int n = an[side];
      if (n == aTick[side].length) { aTick[side] = Arrays.copyOf(aTick[side], 2 * n); aSlug[side] = Arrays.copyOf(aSlug[side], 2 * n); }
      aTick[side][n] = tick; aSlug[side][n] = t.cidSlug[core.s.deckIds[side][slot.getDeckIndex()] + 2];
      an[side]++;
    }

    public int plays(int side) { sync(); return pn[side]; }
    public int presses(int side) { sync(); return an[side]; }

    /** royale_env._Core.act's public_plays form (forms_mode 'deck'), read BEFORE the play is given: 2 when the card's
     *  slot loaded its hero form, else 1 when its next play is evolved (the state's evo row), else 0. */
    public static int playForm(CfCore core, int side, int cid) {
      int[] ids = core.s.deckIds[side];
      for (int i = 0; i < ids.length; i++) {
        if (ids[i] != cid) continue;
        if (core.s.forms[side][i] == 2) return 2;
        var ms = core.s.std.getMatch().side(side);
        return (ms.slotFlags(i) & org.crforge.core.battle.match.MatchSide.EVOLUTION_SLOT) != 0
            && ms.item(i).field() == org.crforge.core.battle.match.EvolutionItem.EVOLVED ? 1 : 0;
      }
      return 0;
    }
  }

  // ---------------------------------------------------------------- state
  static final class Ev {
    int type, tick, seen, slug = -1, form = FORM_PAD, tower = -1, crMe, crOpp, aim = -1, i0, pos;
    boolean mine, xyK, elK, mgK, isXb, isRk;
    double x = -1.0, y = -1.0, el, mg, cost, lost = Double.NaN;
    int[] reach;                                   // X-Bow: reach princesses (TOWER index), null = unknown
    double[] gC, xC, rC;                           // cached outcomes (window closed): {enemy, own, value} / {locked, dmg} / {tower, value}
    // this events() call
    double[] g, xb, rk;
    int ans;
    Ev ansEv;
    double ansDist;
    boolean isAns, combo;
  }

  record Key(int tick, int side, int slug, boolean ab, boolean xyK, double x, double y) {}

  final CfCore core;
  final Tables T;
  final Log log;
  public final int seat;
  // samples
  int ns;
  int[] st = new int[256];
  double[] shp = new double[256 * 6], sel = new double[256];
  boolean[] sal = new boolean[256 * 6];
  final ArrayList<double[]> units = new ArrayList<>();   // per sample: {uid, rel, key, hp, mx, x, y} x n; null = evicted
  @SuppressWarnings({"unchecked", "rawtypes"})
  final HashMap<Integer, ArrayList<double[]>>[] topHist = new HashMap[] {new HashMap<>(), new HashMap<>()};  // {sample, max}
  @SuppressWarnings({"unchecked", "rawtypes"})
  final HashMap<Integer, Double>[] topNow = new HashMap[] {new HashMap<>(), new HashMap<>()};
  final double[] ref = new double[6];
  final int[] lastDmg = new int[6], up = new int[6];
  // events
  final ArrayList<Ev> sorted = new ArrayList<>();
  final HashSet<Key> keys = new HashSet<>();
  int oppPtr, playPtr, pressPtr, unitsFrom, lastT = -1;
  public int late;
  // diagnostics (cumulative)
  public long nanosObserve, nanosFeatures, rows, events, maxEvents;
  // frame scratch
  final double[] fhp = new double[6];
  final boolean[] fal = new boolean[6];
  double fel;
  final ArrayList<double[]> fu = new ArrayList<>();
  // events() scratch
  Ev[] vis = new Ev[64], on = new Ev[64];
  int nv, non;

  public CfMem(CfCore core, Tables t, Log log, int seat) { this.core = core; this.T = t; this.log = log; this.seat = seat; reset(); }

  /** A new match (the loop resets a battle in place). */
  public void reset() {
    ns = nv = non = oppPtr = playPtr = pressPtr = unitsFrom = late = 0;
    lastT = -1;
    units.clear(); sorted.clear(); keys.clear();
    for (int s = 0; s < 2; s++) { topHist[s].clear(); topNow[s].clear(); }
    Arrays.fill(ref, Double.NaN); Arrays.fill(lastDmg, Integer.MIN_VALUE); Arrays.fill(up, -1);
  }

  // ---------------------------------------------------------------- input
  Integer packed(String body, String root) {                    // CfCore.identity without its counters
    Integer p = core.byRoot.get(body + "|" + root);
    return p != null ? p : core.unique.get(body);
  }

  /** sample_sim's board: towers, my elixir, the public bodies. false = a body key is missing (Tables.missing). */
  boolean frame() {
    Arrays.fill(fhp, 0.0);
    Arrays.fill(fal, false);
    fu.clear();
    boolean ok = true;
    for (BattleEntity e : core.s.std.getBattle().getHolder().entities()) {
      if (!(e instanceof WorldEntity w) || !w.getView().isAlive() || CfCore.bombAsSpell(w)) continue;   // state()'s rows
      HitPoints h = w.getHitPoints();
      int hp = h == null ? 0 : h.getHitPoints(), mhp = h == null ? 0 : h.getMaximum();
      if (w instanceof TowerEntity tw) {                           // tower_reads_engine
        double x = w.x();
        if (seat == 1) x = 18000.0 - x;
        int i = 3 * (tw.side() != seat ? 1 : 0) + (tw.getData().king() ? 0 : x / 18000.0 < .5 ? 1 : 2);
        fal[i] = hp > 0;
        fhp[i] = fal[i] ? (mhp != 0 ? (double) hp / (double) mhp : 0.0) : 0.0;
        continue;
      }
      String body = w.getData().name(), root = core.rootCard(w.name());
      Integer p = packed(body, root);
      if (p == null) continue;                                     // card -1: raw() drops it
      if (hp <= 0 && mhp > 0) continue;                            // public_frame: dead with a known max
      int flags = (p & 0xff) | CfObsBind.evolved(w) | (w instanceof CharacterEntity c && core.heroBody(c) ? 16 : 0);
      int form = (flags & 16) != 0 ? 2 : (flags & 8) != 0 ? 1 : 0;   // obs_contract.entity_form
      String k = (p >> 8) + "|" + body + "|" + form;
      Integer v = T.body.get(k);
      if (v == null) { T.missing.add(k + "#" + w.getId()); ok = false; continue; }
      if (v < 0) continue;
      double x = w.x(), y = w.y();
      if (seat == 1) { x = 18000.0 - x; y = 32000.0 - y; }
      fu.add(new double[] {(double) ((long) w.side() << 32 | w.getId()), w.side() != seat ? 1 : 0, v, hp, mhp,
          x / 18000.0, 1.0 - y / 32000.0});
    }
    fel = (double) (core.s.std.getMatch().side(seat).getElixir() / 10) / 1000.0;   // raw()'s elixir_exact
    return ok;
  }

  /** MatchMemory.observe at the seat's decision (tick = the battle's): the board, then the plays known so far (the
   *  seat's CfOppElixir = PublicObserver.plays, updated for this decision first; this side's Log). false = a table entry
   *  is missing (Tables.missing, or a detector key without detSlug): nothing changed; fill and call again. */
  public boolean observe(CfOppElixir opp) {
    long t0 = System.nanoTime();
    final int tick = core.tick();
    if (!frame()) return false;
    for (int i = oppPtr; i < opp.n; i++) if (opp.pkey[i] >= T.detSlug.length) return false;
    log.sync();
    int prev = ns > 0 ? st[ns - 1] : Integer.MIN_VALUE;
    if (ns > 0 && tick < prev) throw new IllegalStateException("CfMem.observe: tick went backwards (reset for a new match)");
    if (ns == 0 || tick > prev) sample(tick);
    final int side = seat, os = 1 - seat;
    for (; oppPtr < opp.n && opp.ticks[oppPtr] <= tick; oppPtr++)   // PublicObserver.plays (tick order)
      play(tick, prev, opp.ticks[oppPtr], os, T.detSlug[opp.pkey[oppPtr]], false, true, opp.px[oppPtr], opp.py[oppPtr],
          opp.pform[oppPtr]);
    for (; playPtr < log.pn[side] && log.pTick[side][playPtr] <= tick; playPtr++)      // env.public_plays
      play(tick, prev, log.pTick[side][playPtr], side, log.pSlug[side][playPtr], false, true, log.pX[side][playPtr],
          log.pY[side][playPtr], log.pForm[side][playPtr]);
    for (; pressPtr < log.an[side] && log.aTick[side][pressPtr] <= tick; pressPtr++)   // own_ability_events
      play(tick, prev, log.aTick[side][pressPtr], side, log.aSlug[side][pressPtr], true, false, 0, 0, FORM_PAD);
    lastT = tick;
    resolve(tick);
    nanosObserve += System.nanoTime() - t0;
    return true;
  }

  void sample(int tick) {
    if (ns == st.length) {
      st = Arrays.copyOf(st, 2 * ns); sel = Arrays.copyOf(sel, 2 * ns);
      shp = Arrays.copyOf(shp, 12 * ns); sal = Arrays.copyOf(sal, 12 * ns);
    }
    int i0 = 6 * ns;
    for (int i = 0; i < 6; i++) { sal[i0 + i] = fal[i]; shp[i0 + i] = fal[i] ? fhp[i] : 0.0; }
    st[ns] = tick;
    sel[ns] = fel;
    ns++;
    for (int i = 0; i < 6; i++) {                                  // tower events, debounced
      if (up[i] < 0) up[i] = fal[i] ? 1 : 0;
      double h = shp[i0 + i], r = ref[i];
      if (Double.isNaN(r) || h > r) ref[i] = h;
      else if (r - h >= DMG_MIN && (lastDmg[i] == Integer.MIN_VALUE || tick - lastDmg[i] >= DMG_GAP)) {
        tower(tick, TDMG, i, r - h);
        ref[i] = h;
        lastDmg[i] = tick;
      }
      if (up[i] == 1 && !fal[i]) { up[i] = 0; tower(tick, TFALL, i, Double.NaN); }
    }
    double[] u = new double[7 * fu.size()];
    for (int j = 0; j < fu.size(); j++) {
      double[] r = fu.get(j);
      System.arraycopy(r, 0, u, 7 * j, 7);
      int rel = (int) r[1], key = (int) r[2];
      double mx = r[4];
      if (mx > topNow[rel].getOrDefault(key, 0.0)) {               // the biggest body of a card so far
        topNow[rel].put(key, mx);
        topHist[rel].computeIfAbsent(key, z -> new ArrayList<>()).add(new double[] {ns - 1, mx});
      }
    }
    units.add(u);
  }

  void tower(int tick, int type, int i, double lost) {
    Ev e = new Ev();
    e.type = type; e.tick = e.seen = tick; e.mine = i < 3; e.tower = i; e.lost = lost;
    e.xyK = true; e.x = TOWER_XY[i][0]; e.y = TOWER_XY[i][1];
    crowns(e, ns - 1);
    e.mgK = true; e.mg = margin(ns - 1);
    insert(e);
  }

  void crowns(Ev e, int i) {
    int o = 6 * i;
    e.crMe = !sal[o + 3] ? 3 : (!sal[o + 4] ? 1 : 0) + (!sal[o + 5] ? 1 : 0);
    e.crOpp = !sal[o] ? 3 : (!sal[o + 1] ? 1 : 0) + (!sal[o + 2] ? 1 : 0);
  }

  double margin(int i) { int o = 6 * i; return (shp[o + 1] + shp[o + 2]) - (shp[o + 4] + shp[o + 5]); }

  /** observe's per-play step: _add with seen = tick for a late play (tick < the previous decision's). */
  void play(int tick, int prev, int tp, int side, int slug, boolean ab, boolean xyK, double px, double py, int form) {
    boolean isLate = prev != Integer.MIN_VALUE && tp < prev;
    if (add(tp, side, slug, ab, xyK, px, py, form, isLate ? tick : tp) && isLate) late++;
  }

  boolean add(int tp, int side, int slug, boolean ab, boolean xyK, double px, double py, int form, int seen) {
    if (slug < 0) return false;                                    // card_key None
    double x = -1.0, y = -1.0;
    if (xyK) {
      if (seat == 1) { px = 18000.0 - px; py = 32000.0 - py; }
      x = px / 18000.0; y = 1.0 - py / 32000.0;
    }
    if (!keys.add(new Key(tp, side, slug, ab, xyK, x, y))) return false;
    Ev e = new Ev();
    e.type = ab ? ABILITY : PLAY; e.tick = tp; e.seen = Math.max(tp, seen); e.mine = side == seat; e.slug = slug;
    e.form = form; e.xyK = xyK; e.x = x; e.y = y;
    int i = bisectLeft(tp) - 1;                                    // the state BEFORE the play
    if (i >= 0) { crowns(e, i); e.mgK = true; e.mg = margin(i); }
    if (e.mine && i >= 0) { e.elK = true; e.el = sel[i]; }
    e.cost = ab ? T.sAbCost[slug] : T.sCost[slug];
    e.i0 = Math.max(i, 0);
    if (slug == T.xbow && !ab) {                                   // reach: alive enemy princesses within XB_REACH
      e.isXb = true;
      int j = bisectRight(tp) - 1;
      if (xyK && j >= 0) {
        int[] q = e.mine ? new int[] {4, 5} : new int[] {1, 2};
        int n = 0;
        int[] r = new int[2];
        for (int k : q) if (shp[6 * j + k] > 0 && tiles(x, y, TOWER_XY[k][0], TOWER_XY[k][1]) <= XB_REACH) r[n++] = k;
        e.reach = Arrays.copyOf(r, n);
      }
    }
    if (slug == T.rocket && e.mine && !ab) {
      e.isRk = true;
      if (xyK) {
        double best = 0;
        int bq = -1;
        for (int q = 3; q <= 5; q++) {
          double d = tiles(x, y, TOWER_XY[q][0], TOWER_XY[q][1]);
          if (bq < 0 || d < best) { best = d; bq = q; }
        }
        e.aim = best <= RK_TOWER_R ? bq : -1;
      }
    }
    insert(e);
    return true;
  }

  static int cmp(Ev a, Ev b) {                                     // match_memory._order
    if (a.tick != b.tick) return Integer.compare(a.tick, b.tick);
    int ta = a.type, tb = b.type;
    if (ta != tb) return Integer.compare(ta, tb);
    if (a.mine != b.mine) return a.mine ? -1 : 1;
    return 0;
  }

  int cmpFull(Ev a, Ev b) {
    int c = cmp(a, b);
    if (c != 0) return c;
    c = (a.slug < 0 ? "" : T.slug.get(a.slug)).compareTo(b.slug < 0 ? "" : T.slug.get(b.slug));
    if (c != 0) return c;
    if (a.tower != b.tower) return Integer.compare(a.tower, b.tower);
    if (a.x != b.x) return a.x < b.x ? -1 : 1;
    if (a.y != b.y) return a.y < b.y ? -1 : 1;
    return 0;
  }

  void insert(Ev e) {                                              // sorted() is stable: after its equals
    int lo = 0, hi = sorted.size();
    while (lo < hi) { int m = (lo + hi) >>> 1; if (cmpFull(sorted.get(m), e) <= 0) lo = m + 1; else hi = m; }
    sorted.add(lo, e);
  }

  int bisectLeft(int x) { int lo = 0, hi = ns; while (lo < hi) { int m = (lo + hi) >>> 1; if (st[m] < x) lo = m + 1; else hi = m; } return lo; }
  int bisectRight(int x) { int lo = 0, hi = ns; while (lo < hi) { int m = (lo + hi) >>> 1; if (st[m] <= x) lo = m + 1; else hi = m; } return lo; }

  static double tiles(double ax, double ay, double bx, double by) { return pyHypot((ax - bx) * TILES_X, (ay - by) * TILES_Y); }

  // ---------------------------------------------------------------- outcomes
  /** Each outcome whose window has closed at {@code tick} is computed now (as features(tick) would, once), then the
   *  bodies no open window can read any more are dropped. */
  void resolve(int tick) {
    int keep = Math.max(ns - 2, 0);
    for (Ev e : sorted) {
      if (e.type > ABILITY) continue;
      if (e.gC == null) { if (e.tick + W_OUT < tick) e.gC = generic(e); else keep = Math.min(keep, e.i0); }
      if (e.isRk && e.rC == null) { if (e.tick + RK_WIN < tick) e.rC = rocket(e); else keep = Math.min(keep, e.i0); }
      if (e.isXb && e.xC == null && e.reach != null && e.reach.length > 0 && e.tick + XB_WINDOW < tick) e.xC = xbow(e);
    }
    for (; unitsFrom < keep; unitsFrom++) units.set(unitsFrom, null);
  }

  double lost(int[] idx, int i0, int i1) {
    if (i0 < 0 || i1 < 0) return Double.NaN;
    double[] a = new double[idx.length];
    for (int k = 0; k < idx.length; k++) { double d = shp[6 * i0 + idx[k]] - shp[6 * i1 + idx[k]]; a[k] = d > 0.0 ? d : 0.0; }
    return pySum(a, a.length);
  }

  static final int[] OPP3 = {3, 4, 5}, MY3 = {0, 1, 2};

  double[] generic(Ev e) {
    int i0 = bisectLeft(e.tick) - 1, i1 = bisectRight(e.tick + W_OUT) - 1;
    int[] en = e.mine ? OPP3 : MY3, own = e.mine ? MY3 : OPP3;
    return new double[] {lost(en, i0, i1), lost(own, i0, i1), removed(e, e.mine ? 1 : 0, i0, i1, VALUE_R)};
  }

  double[] xbow(Ev e) {
    int i0 = bisectRight(e.tick) - 1, lo = bisectRight(e.tick), hi = bisectRight(e.tick + XB_WINDOW);
    boolean locked = false;
    double dmg = 0.0;
    for (int j : e.reach) {
      if (lo >= hi) continue;
      double mn = Double.POSITIVE_INFINITY;
      for (int k = lo; k < hi; k++) mn = Math.min(mn, shp[6 * k + j]);
      double d = shp[6 * i0 + j] - mn;
      locked |= d >= XB_LOCK;
      dmg += d > 0.0 ? d : 0.0;
    }
    return new double[] {locked ? 1 : 0, dmg};
  }

  double[] rocket(Ev e) {
    int i0 = bisectLeft(e.tick) - 1, i1 = bisectRight(e.tick + RK_WIN) - 1;
    return new double[] {e.aim < 0 ? Double.NaN : lost(new int[] {e.aim}, i0, i1), removed(e, 1, i0, i1, RK_R)};
  }

  /** The value the target side's bodies lost between their first sample within radius of the play and sample i1. */
  double removed(Ev e, int target, int i0, int i1, double radius) {
    i0 = Math.max(i0, 0);
    if (!e.xyK || i1 < i0) return Double.NaN;
    LinkedHashMap<Long, double[]> first = new LinkedHashMap<>();
    for (int i = i0; i <= i1; i++) {
      double[] u = units.get(i);
      if (u == null) throw new IllegalStateException("CfMem: bodies of sample " + i + " were dropped (a late play?)");
      for (int j = 0; j < u.length; j += 7)
        if ((int) u[j + 1] == target && !first.containsKey((long) u[j]) && tiles(u[j + 5], u[j + 6], e.x, e.y) <= radius)
          first.put((long) u[j], new double[] {u[j + 2], u[j + 3], u[j + 4]});
    }
    double[] end = units.get(i1);
    double out = 0.0;
    for (Map.Entry<Long, double[]> f : first.entrySet()) {
      double[] b = f.getValue();
      double v0 = value((int) b[0], b[1], b[2], target, i1);
      if (Double.isNaN(v0) || v0 == 0.0) continue;
      double v1 = 0.0;
      for (int j = 0; j < end.length; j += 7)
        if ((long) end[j] == f.getKey()) { double v = value((int) end[j + 2], end[j + 3], end[j + 4], target, i1); v1 = Double.isNaN(v) ? 0.0 : v; break; }
      double d = v0 - v1;
      out += d > 0.0 ? d : 0.0;
    }
    return out;
  }

  /** match_memory._value (habit_terms.body_value, then a building at its cost x hp fraction); NaN = None. */
  double value(int key, double hp, double mx, int side, int i1) {
    double v = Double.NaN, h = hp > 0 ? hp : 0.0, m = mx > 1 ? mx : 1.0;
    if (!T.uNoBody[key] && !(mx < 20)) {
      double top = top(side, T.uTop[key], i1, mx);
      boolean child = mx < .45 * top || T.uSpellChild[key];
      v = (child ? CHILD_VALUE : T.uBase[key]) * h / m;
    }
    if (Double.isNaN(v) && mx >= 20 && T.uBld[key]) v = T.uBldCost[key] * h / m;
    return v;
  }

  double top(int side, int key, int i1, double dflt) {             // top[i1][side].get(key, dflt)
    ArrayList<double[]> h = topHist[side].get(key);
    if (h == null) return dflt;
    double v = dflt;
    boolean found = false;
    for (double[] c : h) { if (c[0] > i1) break; v = c[1]; found = true; }
    return found ? v : dflt;
  }

  // ---------------------------------------------------------------- events(t)
  /** MatchMemory.events(t) into vis[0 .. nv): visibility, outcomes where their windows closed (temp: an uncached one is
   *  computed and not kept, as table() runs it), X-Bow answers, Rocket combos. */
  void events(int t, boolean temp) {
    nv = 0;
    for (Ev e : sorted) {
      if (e.tick >= t) break;
      if (e.seen > t) continue;
      if (nv == vis.length) vis = Arrays.copyOf(vis, 2 * nv);
      e.isAns = false; e.combo = false; e.ans = PENDING; e.ansEv = null; e.g = e.xb = e.rk = null;
      if (e.type <= ABILITY) {
        if (e.tick + W_OUT < t) e.g = e.gC != null ? e.gC : temp ? generic(e) : (e.gC = generic(e));
        if (e.isXb && e.reach != null && e.reach.length > 0 && e.tick + XB_WINDOW < t)
          e.xb = e.xC != null ? e.xC : temp ? xbow(e) : (e.xC = xbow(e));
        if (e.isRk && e.tick + RK_WIN < t) e.rk = e.rC != null ? e.rC : temp ? rocket(e) : (e.rC = rocket(e));
      }
      vis[nv++] = e;
    }
    non = 0;
    for (int i = 0; i < nv; i++)
      if (vis[i].type == PLAY && vis[i].seen == vis[i].tick) { if (non == on.length) on = Arrays.copyOf(on, 2 * non); on[non++] = vis[i]; }
    for (int i = 0; i < nv; i++) {
      Ev d = vis[i];
      if (d.type != PLAY) continue;
      if (d.isXb) {
        Ev a = null;
        if (d.xyK)
          for (int k = 0; k < non; k++) {
            Ev q = on[k];
            if (q.mine != d.mine && d.tick < q.tick && q.tick <= d.tick + XB_ANSWER_T && q.xyK && (q.x < .5) == (d.x < .5)
                && tiles(q.x, q.y, d.x, d.y) <= XB_ANSWER_R) { a = q; break; }
          }
        if (a != null) { a.isAns = true; d.ans = FOUND; d.ansEv = a; d.ansDist = tiles(a.x, a.y, d.x, d.y); }
        else d.ans = d.xyK && t > d.tick + XB_ANSWER_T ? NONE_ANS : PENDING;
      }
      if (d.rk != null)
        for (int k = 0; k < non; k++) {
          Ev q = on[k];
          if (q.mine && q.slug == T.tornado && COMBO_LO <= d.tick - q.tick && d.tick - q.tick <= COMBO_HI) { d.combo = true; break; }
        }
    }
  }

  /** match_memory._row(e, t) into v[o .. o + F) (zeroed by the caller), float32 as numpy stores it. */
  void row(Ev e, int t, float[] v, int o) {
    int tp = e.tick;
    v[o + e.type] = 1f;
    v[o + MINE] = e.mine ? 1f : 0f;
    v[o + AGO] = (float) ((t - tp) * TICK_S / 60);
    v[o + T300] = (float) (tp * TICK_S / 300);
    v[o + PH1 + (tp < DOUBLE_T ? 0 : tp < OT_T ? 1 : 2)] = 1f;
    v[o + CRM] = (float) (e.crMe / 3.0);
    v[o + CRO] = (float) (e.crOpp / 3.0);
    if (e.xyK) { v[o + X] = (float) e.x; v[o + Y] = (float) e.y; v[o + XYK] = 1f; }
    if (e.elK) { v[o + EL10] = (float) (e.el / 10); v[o + ELK] = 1f; }
    if (e.mgK) { v[o + MG2] = (float) (e.mg / 2); v[o + MGK] = 1f; }
    if (e.tower >= 0) {
      v[o + TK + e.tower % 3] = 1f;
      v[o + TLOST] = (float) (Double.isNaN(e.lost) ? 0.0 : e.lost);
      return;
    }
    v[o + COST10] = (float) (e.cost / 10);
    if (e.g != null) {
      v[o + OUT_DONE] = 1f;
      if (!Double.isNaN(e.g[0]) && !Double.isNaN(e.g[1])) { v[o + OUT_EN] = (float) e.g[0]; v[o + OUT_OWN] = (float) e.g[1]; v[o + OUT_TK] = 1f; }
      if (!Double.isNaN(e.g[2])) { v[o + OUT_V10] = (float) (e.g[2] / 10); v[o + OUT_VK] = 1f; }
    }
    if (e.reach != null && e.reach.length > 0) v[o + XB_REACH_F] = 1f;
    if (e.xb != null) {
      boolean lk = e.xb[0] != 0;
      v[o + XB_DONE] = 1f; v[o + XB_LOCKED] = lk ? 1f : 0f; v[o + XB_FAILED] = lk ? 0f : 1f; v[o + XB_DMG] = (float) e.xb[1];
    }
    if (e.isXb && e.ans != PENDING) {
      v[o + XB_ANS_DONE] = 1f;
      v[o + XB_ANSWERED] = e.ans == FOUND ? 1f : 0f;
      if (e.ans == FOUND) v[o + XB_ANS_DIST] = (float) (e.ansDist / XB_ANSWER_R);
    }
    if (e.isAns) v[o + IS_XB_ANS] = 1f;
    if (e.aim >= 0) v[o + RK_TOWER] = 1f;
    if (e.rk != null) {
      v[o + RK_DONE] = 1f;
      v[o + RK_COMBO] = e.combo ? 1f : 0f;
      if (!Double.isNaN(e.rk[0])) { v[o + RK_TLOST] = (float) e.rk[0]; v[o + RK_TK] = 1f; }
      if (!Double.isNaN(e.rk[1])) { v[o + RK_V10] = (float) (e.rk[1] / 10); v[o + RK_VK] = 1f; }
    }
  }

  // ---------------------------------------------------------------- features(t)
  final float[] evRow = new float[E_MAX * F];
  final float[] sum = new float[S_V2];

  /** MatchMemory.features(t, gid, deck, 'v2') at the last observe's tick into {@code out} at {@code off} (layout OFF_*).
   *  deck = the row's deck_card (8 gid ids, the model's order). */
  public void features(int[] deck, ByteBuffer out, int off) {
    long t0 = System.nanoTime();
    final int t = lastT;
    events(t, false);
    Arrays.fill(evRow, 0f);
    int nr = Math.min(nv, E_MAX);
    for (int r = 0; r < nr; r++) row(vis[nv - 1 - r], t, evRow, r * F);
    floats(out, off + OFF_EV, evRow);
    for (int r = 0; r < E_MAX; r++) {
      Ev e = r < nr ? vis[nv - 1 - r] : null;
      out.put(off + OFF_MASK + r, (byte) (e != null ? 1 : 0));
      out.putLong(off + OFF_CARD + 8 * r, e != null && e.slug >= 0 ? T.sGid[e.slug] : 0);
      out.putLong(off + OFF_FORM + 8 * r, e != null && e.slug >= 0 ? e.form : FORM_PAD);
    }
    long ans = summary(t, deck);
    double[] f = s1c(t);
    for (int i = 0; i < N_S1C; i++) sum[S + i] = (float) f[i];
    floats(out, off + OFF_SUM, sum);
    out.putLong(off + OFF_ANS, ans);
    rows++;
    events += nv;
    maxEvents = Math.max(maxEvents, nv);
    nanosFeatures += System.nanoTime() - t0;
  }

  /** A bulk float copy into {@code out} at byte {@code at} (in out's byte order). */
  static void floats(ByteBuffer out, int at, float[] v) {
    ByteBuffer d = out.duplicate().order(out.order());
    d.position(at);
    d.asFloatBuffer().put(v);
  }

  /** Cost probe (steady-state JIT): features() at the last tick {@code reps} times into a scratch buffer; ns per call.
   *  Repeating it changes nothing a later row reads (every outcome it shows is cached already). */
  public long benchFeatures(int[] deck, int reps) {
    ByteBuffer b = ByteBuffer.allocateDirect(BYTES).order(java.nio.ByteOrder.nativeOrder());
    long r0 = rows, e0 = events, n0 = nanosFeatures, t0 = System.nanoTime();
    for (int i = 0; i < reps; i++) features(deck, b, 0);
    long ns = (System.nanoTime() - t0) / Math.max(reps, 1);
    rows = r0; events = e0; nanosFeatures = n0;
    return ns;
  }

  /** match_memory.summary over vis -> sum[0 .. S) (float32), returns mem_answer. */
  long summary(int t, int[] deck) {
    Arrays.fill(sum, 0f);
    int nXb = 0, nDone = 0, nLocked = 0, nReach = 0, since = 0, lastLocked = 0, nAns = 0, nRk = 0, nRkt = 0, nCombo = 0;
    double[] dmg = new double[nv], rkt = new double[nv];
    int nRktSum = 0;
    int[] found = new int[nv];
    int nFound = 0;
    for (int i = 0; i < nv; i++) {
      Ev e = vis[i];
      if (e.type != PLAY || !e.mine) continue;
      if (e.slug == T.xbow) {
        nXb++;
        if (e.reach != null && e.reach.length > 0) {
          nReach++;
          if (e.xb != null) {
            dmg[nDone++] = e.xb[1];
            if (e.xb[0] != 0) { nLocked++; lastLocked = e.tick; since = 0; } else since++;
          }
        }
        if (e.ans != PENDING) { nAns++; if (e.ans == FOUND) found[nFound++] = T.sGid[e.ansEv.slug]; }
      }
      if (e.slug == T.rocket) {
        nRk++;
        if (e.aim >= 0) { nRkt++; if (e.rk != null) rkt[nRktSum++] = Double.isNaN(e.rk[0]) ? 0.0 : e.rk[0]; }
        if (e.rk != null && e.combo) nCombo++;
      }
    }
    double[] s = new double[S];
    s[0] = nXb / 10.0; s[1] = nDone / 10.0; s[2] = nLocked / 10.0; s[3] = (nDone - nLocked) / 10.0;
    s[4] = (nReach - nDone) / 10.0; s[5] = since / 10.0; s[6] = mean(dmg, nDone); s[7] = nLocked > 0 ? 1 : 0;
    s[8] = nLocked > 0 ? (t - lastLocked) * TICK_S / 60 : 0.0; s[9] = nAns > 0 ? (double) nFound / nAns : 0.0;
    s[10] = nRkt / 5.0; s[11] = pySum(rkt, nRktSum); s[12] = nRk / 5.0; s[13] = nCombo / 5.0;
    double[] sw = new double[nv], vp = new double[nv];
    for (int k = 0; k < Math.min(deck.length, DECK_N); k++) {
      int c = deck[k], nPs = 0, nSw = 0, nVp = 0;
      for (int i = 0; i < nv && c != 0; i++) {
        Ev e = vis[i];
        if (e.type != PLAY || !e.mine || T.sGid[e.slug] != c) continue;
        nPs++;
        if (e.g == null) continue;
        if (!Double.isNaN(e.g[0]) && !Double.isNaN(e.g[1])) sw[nSw++] = e.g[0] - e.g[1];
        if (!Double.isNaN(e.g[2]) && e.cost > 0) vp[nVp++] = e.g[2] / e.cost;
      }
      int o = 14 + 5 * k;
      s[o] = nPs / 10.0; s[o + 1] = nSw > 0 ? 1 : 0; s[o + 2] = mean(sw, nSw); s[o + 3] = nVp > 0 ? 1 : 0; s[o + 4] = mean(vp, nVp) / 2;
    }
    for (int i = 0; i < S; i++) sum[i] = (float) s[i];
    HashMap<Integer, int[]> cnt = new HashMap<>();                // most frequent answer card, tie = the latest
    for (int i = 0; i < nFound; i++) { int[] c = cnt.computeIfAbsent(found[i], z -> new int[2]); c[0]++; c[1] = i; }
    long best = 0;
    int[] bk = null;
    for (Map.Entry<Integer, int[]> c : cnt.entrySet()) {
      int[] v = c.getValue();
      if (bk == null || v[0] > bk[0] || (v[0] == bk[0] && v[1] > bk[1])) { bk = v; best = c.getKey(); }
    }
    return best;
  }

  static double mean(double[] a, int n) { return n > 0 ? pySum(a, n) / n : 0.0; }

  /** match_memory._s1c at t over vis (T = 1), float64 [60]. */
  double[] s1c(int t) {
    int nl = T.lutDeck.length;
    int[] lastPos = new int[Math.max(nl, 1)];
    Arrays.fill(lastPos, -1);
    double[] oppTick = new double[nv];
    int nOpp = 0;
    for (int i = 0; i < nv; i++) {
      Ev e = vis[i];
      if (e.type != PLAY || e.mine) continue;
      int c = T.sGid[e.slug];
      if (c > 0 && c < nl) lastPos[c] = i;
      oppTick[nOpp++] = e.tick;
    }
    int nrev = 0;
    for (int c = 1; c < nl; c++) if (lastPos[c] >= 0) nrev++;
    int K = Math.max(nrev, 1);
    int[] cid = new int[K], need = new int[K];
    boolean[] ok = new boolean[K];
    double[] x = new double[K], a = new double[K], d = new double[K];
    int k0 = 0;
    for (int c = 1; c < nl; c++) {
      if (lastPos[c] < 0) continue;
      Ev e = vis[lastPos[c]];
      int since = 0;
      for (int j = 0; j < nOpp; j++) if (oppTick[j] > e.tick) since++;
      cid[k0] = c; ok[k0] = true; need[k0] = Math.max(0, CYCLE - since); x[k0] = roundCost(e.cost);
      a[k0] = T.lutAns[c]; d[k0] = T.lutDeck[c];
      k0++;
    }
    if (nrev == 0) need[0] = CYCLE;
    // OppElixirCounter's rule on the visible opponent plays
    double est = 6.0, at = 0.0;
    for (int i = 0; i < nv; i++) {
      Ev e = vis[i];
      if (e.type != PLAY || e.mine) continue;
      double cost = roundCost(e.cost), R = T.regenCum(e.tick);
      double ee = Math.min(10.0, est + R - at);
      est = Math.max(ee, cost) - cost;
      at = R;
    }
    est = Math.min(10.0, est + T.regenCum(t) - at);
    double meanX = 0.0;
    for (int k = 0; k < K; k++) meanX = k == 0 ? (ok[k] ? x[k] : 0.0) : meanX + (ok[k] ? x[k] : 0.0);
    meanX /= Math.max(nrev, 1);
    double[] pool = new double[K + DECK_N];
    for (int k = 0; k < K; k++) pool[k] = ok[k] ? x[k] : Double.POSITIVE_INFINITY;
    for (int k = 0; k < DECK_N; k++) pool[K + k] = k < DECK_N - nrev ? meanX : Double.POSITIVE_INFINITY;
    Arrays.sort(pool);
    double[] P = new double[CYCLE + 2];
    for (int k = 0; k <= CYCLE; k++) P[k + 1] = k == 0 ? pool[0] : P[k] + pool[k];
    double[] cyc = new double[K];
    boolean ck = false, ready = false;
    boolean[] ctr = new boolean[K];
    for (int k = 0; k < K; k++) {
      int nd = need[k];
      double sk = pool[Math.max(nd - 1, 0)];
      cyc[k] = nd == 0 ? 0.0 : x[k] <= sk ? P[Math.min(nd + 1, CYCLE + 1)] - x[k] : P[nd];
      ctr[k] = ok[k] && a[k] < COUNTER_LIFT;
      ck |= ctr[k];
      ready |= ctr[k] && nd == 0 && est >= x[k];
    }
    double[] f = new double[N_S1C];
    boolean has = nrev > 0;
    double minD = Double.POSITIVE_INFINITY, minA = Double.POSITIVE_INFINITY, negD = 0.0, ctrCyc = Double.POSITIVE_INFINITY;
    int ctrNeed = CYCLE;
    for (int k = 0; k < K; k++) {
      if (ok[k]) { minD = Math.min(minD, d[k]); minA = Math.min(minA, a[k]); }
      double nd = Math.min(d[k], 0.0);
      negD = k == 0 ? nd : negD + nd;
      if (ctr[k]) { ctrNeed = Math.min(ctrNeed, need[k]); ctrCyc = Math.min(ctrCyc, cyc[k]); }
    }
    f[0] = Math.min(nrev, DECK_N) / (double) DECK_N;
    f[1] = has ? minD : 0.0;
    f[2] = negD;
    f[3] = has ? minA : 0.0;
    f[4] = ck ? 1 : 0;
    f[5] = ctrNeed / (double) CYCLE;
    f[6] = (ck ? ctrCyc : 0.0) / 10;
    f[7] = est / 10;
    f[8] = ready ? 1 : 0;
    Integer[] order = new Integer[K];
    for (int k = 0; k < K; k++) order[k] = k;
    final double[] key = new double[K];
    for (int k = 0; k < K; k++) key[k] = ok[k] ? a[k] : Double.POSITIVE_INFINITY;
    Arrays.sort(order, (p, q) -> key[p] != key[q] ? (key[p] < key[q] ? -1 : 1) : Integer.compare(cid[p], cid[q]));
    for (int sI = 0; sI < Math.min(K, SLOT_N); sI++) {
      int k = order[sI];
      if (!ok[k]) continue;
      int o = 9 + 5 * sI;
      f[o] = 1.0; f[o + 1] = need[k] / (double) CYCLE; f[o + 2] = x[k] / 10; f[o + 3] = a[k]; f[o + 4] = d[k];
    }
    king(t, true, f, 49);
    king(t, false, f, 51);
    double[] m0 = marginAt(t), m30 = marginAt(t - 600), m60 = marginAt(t - 1200);
    f[53] = m0[0] / 2; f[54] = m0[1]; f[55] = (m0[0] - m30[0]) / 2; f[56] = (m0[0] - m60[0]) / 2;
    f[57] = m0[1] - m30[1]; f[58] = m0[1] - m60[1];
    // the frozen lock head: LOCK_INPUTS = the v1 summary's first 14 (float32), f[0 .. 59), game time, phase
    double[] in = new double[N_LOCK];
    for (int i = 0; i < 14; i++) in[i] = sum[i];
    System.arraycopy(f, 0, in, 14, N_S1C - 1);
    in[73] = t * TICK_S / 300;
    in[74] = t < DOUBLE_T ? 1 : 0; in[75] = t >= DOUBLE_T && t < OT_T ? 1 : 0; in[76] = t >= OT_T ? 1 : 0;
    double z = 0.0;
    for (int i = 0; i < N_LOCK; i++) {
      double term = (in[i] - T.lockMean[i]) / T.lockStd[i] * T.lockW[i];
      z = i == 0 ? term : z + term;
    }
    z += T.lockB;
    f[59] = 1.0 / (1.0 + StrictMath.exp(-z));
    return f;
  }

  /** np.round(float64(float32(cost / 10)) * 10, 1). */
  static double roundCost(double cost) {
    double c = (double) (float) (cost / 10) * 10;
    return Math.rint(c * 10.0) / 10.0;
  }

  void king(int t, boolean mine, double[] f, int o) {
    int first = Integer.MAX_VALUE;
    for (int i = 0; i < nv; i++) {
      Ev e = vis[i];
      if (e.mine != mine || e.tower < 0) continue;
      if ((e.type == TDMG && e.tower % 3 == 0) || e.type == TFALL) first = Math.min(first, e.tick);
    }
    boolean on = first != Integer.MAX_VALUE;
    f[o] = on ? 1 : 0;
    f[o + 1] = on ? (t - first) * TICK_S / 60 : 0.0;
  }

  /** _s1c's margin(cut): {princesses (enemy - mine), kings (enemy - mine)} of the tower HP lost, events with tick < cut. */
  double[] marginAt(int cut) {
    double[][] hp = new double[2][3];
    for (int side = 0; side < 2; side++)
      for (int tw = 0; tw < 3; tw++) {
        boolean fell = false;
        double s = 0.0;
        for (int i = 0; i < nv; i++) {
          Ev e = vis[i];
          if (e.tick >= cut || e.tower < 0 || e.mine != (side == 1) || e.tower % 3 != tw) continue;
          if (e.type == TFALL) fell = true;
          else s += (double) (float) (Double.isNaN(e.lost) ? 0.0 : e.lost);
        }
        hp[side][tw] = fell ? 1.0 : Math.min(1.0, s);
      }
    return new double[] {(hp[0][1] + hp[0][2]) - (hp[1][1] + hp[1][2]), hp[0][0] - hp[1][0]};
  }

  // ---------------------------------------------------------------- table()
  /** match_memory.TABLE_KEYS arrays of one match (row-major; dtypes as numpy: tick / vis / res / card / ansCard int32,
   *  vals float32, form / flag int8, the rest float64). */
  public static final class Table {
    public int n;
    public int[] tick, vis, res, card, ansCard;
    public float[] vals;
    public byte[] form, flag;
    public double[] xbDmg, rkTl, swing, vpe;
  }

  /** MatchMemory.table(gid) now (call at the END of the match; an open window's outcome is computed from the samples so
   *  far and not kept). */
  public Table table() {
    events(NEVER, true);
    int n = nv;
    Table b = new Table();
    b.n = n;
    b.tick = new int[n]; b.vis = new int[n]; b.res = new int[6 * n]; b.card = new int[n]; b.ansCard = new int[n];
    b.vals = new float[F * n]; b.form = new byte[n]; b.flag = new byte[n];
    b.xbDmg = new double[n]; b.rkTl = new double[n]; b.swing = new double[n]; b.vpe = new double[n];
    for (int i = 0; i < n; i++) vis[i].pos = i;
    for (int i = 0; i < n; i++) {
      Ev d = vis[i];
      b.tick[i] = d.tick;
      b.vis[i] = Math.max(d.tick + 1, d.seen);
      row(d, d.tick, b.vals, F * i);
      b.vals[F * i + AGO] = 0f;
      boolean card = d.slug >= 0;
      b.card[i] = card ? T.sGid[d.slug] : 0;
      b.form[i] = (byte) (card ? d.form : FORM_PAD);
      if (card) for (int g = 1; g < 6; g++) b.res[6 * i + g] = NEVER;
    }
    for (int i = 0; i < n; i++) {
      Ev d = vis[i];
      if (d.slug < 0) continue;
      int tp = d.tick;
      b.res[6 * i + 1] = tp + W_OUT + 1;
      double[] o = d.g;
      if (!Double.isNaN(o[0]) && !Double.isNaN(o[1])) b.swing[i] = o[0] - o[1];
      if (!Double.isNaN(o[2]) && d.cost > 0) b.vpe[i] = o[2] / d.cost;
      boolean own = d.type == PLAY && d.mine;
      if (d.isXb) {
        b.flag[i] |= (byte) (own ? 1 : 0);
        if (d.reach != null && d.reach.length > 0) { b.res[6 * i + 2] = tp + XB_WINDOW + 1; b.xbDmg[i] = d.xb[1]; }
        if (d.ans != PENDING) {
          Ev a = d.ansEv;
          b.res[6 * i + 3] = a != null ? a.tick + 1 : tp + XB_ANSWER_T + 1;
          if (a != null) {
            b.ansCard[i] = T.sGid[a.slug];
            b.flag[i] |= 4;
            int j = a.pos;
            b.res[6 * j + 4] = Math.min(b.res[6 * j + 4], Math.max(a.tick + 1, b.vis[i]));
          }
        }
      }
      if (d.isRk) {
        b.flag[i] |= (byte) (2 * (own ? 1 : 0));
        b.res[6 * i + 5] = tp + RK_WIN + 1;
        b.rkTl[i] = Double.isNaN(d.rk[0]) ? 0.0 : d.rk[0];
      }
    }
    return b;
  }

  // ---------------------------------------------------------------- CPython / numpy arithmetic
  /** CPython (>= 3.12) builtin sum() of n floats with start 0: 0 + x0, then Neumaier compensation. */
  public static double pySum(double[] a, int n) {
    if (n == 0) return 0.0;
    double f = 0.0 + a[0], c = 0.0;
    for (int i = 1; i < n; i++) {
      double x = a[i], t = f + x;
      if (Math.abs(f) >= Math.abs(x)) c += (f - t) + x;
      else c += (x - t) + f;
      f = t;
    }
    if (c != 0.0 && Double.isFinite(c)) f += c;
    return f;
  }

  /** CPython (>= 3.12) math.hypot(a, b): vector_norm (scaled, error-free squares, a differential correction). */
  public static double pyHypot(double a, double b) {
    a = Math.abs(a); b = Math.abs(b);
    double max = Math.max(a, b);
    if (Double.isInfinite(max)) return max;
    if (Double.isNaN(a) || Double.isNaN(b)) return Double.NaN;
    if (max == 0.0) return max;
    if (max < Double.MIN_NORMAL) return Math.hypot(a, b);         // ponytail: never on the board (subnormal steps)
    int maxE = Math.getExponent(max) + 1;                          // frexp's exponent
    double scale = Math.scalb(1.0, -maxE), csum = 1.0, frac1 = 0.0, frac2 = 0.0;
    for (int i = 0; i < 2; i++) {
      double x = (i == 0 ? a : b) * scale;
      double hi = x * x, lo = Math.fma(x, x, -hi);
      double s = csum + hi, sl = (csum - s) + hi;
      csum = s; frac1 += lo; frac2 += sl;
    }
    double h = Math.sqrt(csum - 1.0 + (frac1 + frac2));
    double hi = -h * h, lo = Math.fma(-h, h, -hi);
    double s = csum + hi, sl = (csum - s) + hi;
    csum = s; frac1 += lo; frac2 += sl;
    double x = csum - 1.0 + (frac1 + frac2);
    h += x / (2.0 * h);
    return h / scale;
  }

  /** Test hooks for obs_id.py's arithmetic self-check (vectors in, vectors out). */
  public static double[] hypots(double[] a, double[] b) {
    double[] o = new double[a.length];
    for (int i = 0; i < a.length; i++) o[i] = pyHypot(a[i], b[i]);
    return o;
  }

  public static double[] sums(double[] flat, int[] len) {
    double[] o = new double[len.length];
    int p = 0;
    for (int i = 0; i < len.length; i++) { o[i] = pySum(Arrays.copyOfRange(flat, p, p + len[i]), len[i]); p += len[i]; }
    return o;
  }

  public static double[] sigmoids(double[] z) {
    double[] o = new double[z.length];
    for (int i = 0; i < z.length; i++) o[i] = 1.0 / (1.0 + StrictMath.exp(-z[i]));
    return o;
  }

  public static double[] roundCosts(double[] c) {
    double[] o = new double[c.length];
    for (int i = 0; i < c.length; i++) o[i] = roundCost(c[i]);
    return o;
  }
}
