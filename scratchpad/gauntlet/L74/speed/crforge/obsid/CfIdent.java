// S3b-3b (plan1026 Pillar 4): the GenModel row's past plays and hand / deck identity arrays, built in Java from the F1
// facade's battle (CfCore) and the loop's own accepted plays, as e1_eval.GenPolicy.slot_ident + GenPolicy.row +
// dataset._past make them (feature version 6). Default package, beside CfCore: reads its package-private St.

import java.nio.FloatBuffer;
import java.nio.LongBuffer;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import org.crforge.core.battle.match.MatchSide;

public final class CfIdent {
  public static final int SLOTS = 8, PAST_K = 3, FORM_PAD = 3, IDS = 48, PAST = PAST_K * 5;

  /** RoyaleSim catalogue card id -> the checkpoint's card id (dataset_gen.checkpoint_gid of card_key(name)); Python
   *  fills it (putGid: JPype would box a Python int key as a Long). A deck card missing here throws, as slot_ident
   *  raises on a card outside the card_vocab. */
  final HashMap<Integer, Integer> gid = new HashMap<>();
  public void putGid(int cardId, int id) { gid.put(cardId, id); }
  public int gx = 36, gy = 64;        // model_v3.GRID_X / GRID_Y
  public double cellOff;              // model_v3.cell_xy: 0 = "lattice", 0.5 = "floor"
  public int extrap;                  // cfg extrapolate_ticks: a seat's view tick = tick + it from its 2nd decision

  Object std;                         // the battle the play log and the decided flags belong to
  final int[][] tk = new int[2][64], sl = new int[2][64], cl = new int[2][64];
  final int[] n = new int[2];
  final boolean[] decided = new boolean[2];

  void sync(CfCore core) {
    if (std != core.s.std) { std = core.s.std; n[0] = n[1] = 0; decided[0] = decided[1] = false; }
  }

  /** A play the facade GAVE (CfCore.play refusal 0) at facade tick {@code tick}: our deck slot and the decided cell
   *  (e1_eval.Match._land's done_plays entry: the landing tick, the slot, cell_center of the cell). */
  public void played(CfCore core, int seat, int tick, int slot, int cell) {
    sync(core);
    int i = n[seat]++;
    if (i == tk[seat].length) {
      tk[seat] = Arrays.copyOf(tk[seat], 2 * i); sl[seat] = Arrays.copyOf(sl[seat], 2 * i); cl[seat] = Arrays.copyOf(cl[seat], 2 * i);
    }
    tk[seat][i] = tick; sl[seat][i] = slot; cl[seat][i] = cell;
  }

  /**
   * {@code seat}'s identity arrays and past plays at this decision; {@code slotOf} = crforge deck index (the deal
   * order) -> our deck slot (8 = none). ids (int64, 48): hand_slot[4] hand_card[4] hand_form[4] next_card next_form
   * deck_card[8] deck_form[8] slot_card[9] slot_form[9]. past (float32, 3 x 5): (card, form, x, y, seconds ago),
   * newest first, plays landed strictly before the view tick; none = (0, 3, -1, -1, -1).
   */
  public void build(CfCore core, int seat, int[] slotOf, LongBuffer ids, int idsOff, FloatBuffer past, int pastOff) {
    sync(core);
    int view = core.tick() + (decided[seat] ? extrap : 0);   // e1_eval.Match.prepare: h = 0 on a seat's first decision
    decided[seat] = true;
    // slot_ident: slot s = the deck card at the deal index slotOf maps to s; index 8 = pad (0, FORM_PAD)
    long[] card = new long[SLOTS + 1], form = new long[SLOTS + 1];
    form[SLOTS] = FORM_PAD;
    int[] ids0 = core.s.deckIds[seat], forms0 = core.s.forms[seat];
    for (int k = 0; k < SLOTS; k++) {
      int s = slotOf[k];
      if (s >= SLOTS) continue;
      Integer g = gid.get(ids0[k]);
      if (g == null) throw new IllegalStateException("seat " + seat + " deck " + Arrays.toString(ids0) + ": card id " + ids0[k] + " not in the checkpoint's card_vocab");
      card[s] = g;
      form[s] = forms0[k];
    }
    MatchSide me = core.s.std.getMatch().side(seat);
    int[] hand = me.getHand().slots();
    List<Integer> q = me.getHand().queue();
    int o = idsOff;
    int[] hs = new int[4];
    for (int h = 0; h < 4; h++) hs[h] = h < hand.length && hand[h] >= 0 ? slotOf[hand[h]] : SLOTS;   // = the sc one-hot
    for (int h = 0; h < 4; h++) ids.put(o++, hs[h]);
    for (int h = 0; h < 4; h++) ids.put(o++, card[hs[h]]);
    for (int h = 0; h < 4; h++) ids.put(o++, form[hs[h]]);
    int ns = q.isEmpty() ? SLOTS : slotOf[q.get(0)];
    ids.put(o++, card[ns]);
    ids.put(o++, form[ns]);
    int[] ord = new int[SLOTS];                                // stable argsort of slot_card[:8]
    for (int i = 0; i < SLOTS; i++) {
      int j = i;
      while (j > 0 && card[ord[j - 1]] > card[i]) { ord[j] = ord[j - 1]; j--; }
      ord[j] = i;
    }
    for (int i = 0; i < SLOTS; i++) ids.put(o++, card[ord[i]]);
    for (int i = 0; i < SLOTS; i++) ids.put(o++, form[ord[i]]);
    for (int i = 0; i <= SLOTS; i++) ids.put(o++, card[i]);
    for (int i = 0; i <= SLOTS; i++) ids.put(o++, form[i]);
    // dataset._past + GenPolicy.row: the last PAST_K plays before the view tick, newest first
    int p = pastOff, got = 0;
    for (int i = n[seat] - 1; i >= 0 && got < PAST_K; i--) {
      if (tk[seat][i] >= view) continue;
      int c = cl[seat][i], s = sl[seat][i];
      past.put(p++, card[s]);
      past.put(p++, form[s]);
      past.put(p++, (float) ((c % gx + cellOff) / gx));
      past.put(p++, (float) ((c / gx + cellOff) / gy));
      past.put(p++, (float) ((view - tk[seat][i]) * 0.05));
      got++;
    }
    for (; got < PAST_K; got++) {
      past.put(p++, 0f); past.put(p++, FORM_PAD); past.put(p++, -1f); past.put(p++, -1f); past.put(p++, -1f);
    }
  }
}
