"""Observer-only IWDIAG telemetry. No engine imports and no policy inputs.

Tower damage is an explicitly labeled public impact-associated HP-loss estimate:
the API has no public per-source damage ledger. It must not be called exact
X-Bow damage. The recorder never reads target_uid, attack timers or snapshots.
"""
from collections import Counter
import math


def public_sample(state, names, tower_kinds):
    return dict(tick=int(state.tick),
                towers={(e.team, e.x, e.y): max(0, e.hp) for e in state.entities if e.kind in tower_kinds},
                shots=[(p.team, names.get(p.firer_card_id), p.x, p.y, p.aim_x, p.aim_y)
                       for p in state.projectiles],
                bodies=[(e.team, e.card_id, e.x, e.y) for e in state.entities
                        if e.kind not in tower_kinds and e.hp > 0],
                spells=[(s.team, s.x, s.y) for s in state.spells])


class Recorder:
    def __init__(self, side, xbow_id, shot_step):
        self.side, self.xbow_id, self.shot_step = side, xbow_id, shot_step
        self.counts = Counter()
        self.elixir = 0.
        self.impacts = []
        self.presses = []

    def observe(self, before, after):
        if after['tick'] != before['tick'] + 1 or before['tick'] >= 6000:
            return  # exclude crown tiebreak drain; never attribute an unsampled interval
        for key, hp in before['towers'].items():
            team, x, y = key
            if team == self.side or hp <= 0:
                continue
            loss = max(0, hp-after['towers'].get(key, 0))
            if not loss:
                continue
            near = [p for p in before['shots'] if p[0] == self.side and p[1] == 'Xbow'
                    and (p[4], p[5]) == (x, y)
                    and math.hypot(p[2]-x, p[3]-y) <= self.shot_step+2]
            if not near:
                continue
            # Conservative collision warning: any other friendly shot aimed at
            # this tower, body within 12 tiles, or spell anywhere may contribute.
            mixed = (any(p[0] == self.side and p[1] != 'Xbow' and (p[4], p[5]) == (x, y)
                         for p in before['shots'])
                     or any(t == self.side and cid != self.xbow_id and math.hypot(bx-x, by-y) <= 216000
                            for t, cid, bx, by in before['bodies'])
                     or any(s[0] == self.side for s in before['spells'] + after['spells']))
            self.counts['xbow_impact_hp_loss'] += loss
            self.counts['xbow_contested_hp_loss'] += loss if mixed else 0
            self.counts['xbow_impact_windows'] += 1
            self.impacts.append(dict(tick=after['tick'], tower=list(key), hp_loss=loss,
                                     visible_arriving_bolts=len(near), possibly_mixed=bool(mixed)))

    def result(self):
        attempted, accepted = self.counts['iw_attempts'], self.counts['iw_accepted']
        return dict(iw_scheduled=self.counts['iw_scheduled'], iw_attempts=attempted,
                    iw_accepted=accepted, iw_elixir=self.elixir,
                    iw_success_rate=accepted/attempted if attempted else None,
                    xbow_placements=self.counts['xbow_placements'],
                    xbow_tower_damage_exact=None,
                    xbow_impact_hp_loss=self.counts['xbow_impact_hp_loss'],
                    xbow_contested_hp_loss=self.counts['xbow_contested_hp_loss'],
                    xbow_impact_windows=self.counts['xbow_impact_windows'],
                    damage_method='public Xbow bolt within one catalog-speed tick of visible tower aim + next-tick HP drop; mixed damage possible; excludes tick >=6000',
                    press_receipts=self.presses, impact_receipts=self.impacts)


def instrument(env, side, shot_step, tower_kinds):
    recorder = Recorder(side, env.ids['Xbow'], shot_step)
    step, act, queue = env.core.step, env.eng.act, env.queue_abilities

    def observed_step(commands, ticks):
        # Keep command application at the original tick. Every subsequent engine
        # tick remains in order; do not insert policy calls or consume any RNG.
        if ticks < 0:
            return step(commands, ticks)
        if not ticks:
            return step(commands, 0)
        # Production adapter only submits commands with ticks=0. Fail rather
        # than silently change a future combined command/advance contract.
        if commands:
            raise ValueError('IWDIAG requires separate deploy and advance calls')
        result = []
        for _ in range(ticks):
            before = public_sample(env.core.state(), env.names, tower_kinds)
            result = step([], 1)
            state = env.core.state()
            recorder.observe(before, public_sample(state, env.names, tower_kinds))
            if state.game_over:
                break
        return result

    def observed_act(**kw):
        own = kw['side'] == side
        button = kw.get('ability_button')
        before = env.core.state() if own and button is not None else None
        iw = before is not None and env.names.get(before.players[side].abilities[button][3]) == 'IceWizard'
        card = env.names[env.deck_ids[side][kw['deck_index']]] if own and button is None else None
        result = act(**kw)
        if iw:
            after = env.core.state()
            spent = (before.players[side].elixir_milli-after.players[side].elixir_milli)/1000
            if spent < 0 or (not result['accepted'] and spent != 0):
                raise ValueError('unexpected zero-tick ability elixir accounting')
            recorder.counts['iw_attempts'] += 1
            recorder.counts['iw_accepted'] += int(result['accepted'])
            recorder.elixir += spent
            recorder.presses.append(dict(tick=int(before.tick), accepted=result['accepted'],
                                         result_code=result['result_code'], spent=spent,
                                         button_cost=before.players[side].abilities[button][2]))
        if card == 'Xbow' and result['accepted']:
            recorder.counts['xbow_placements'] += 1
        return result

    def observed_queue(owner, commands, delay):
        pending = {(s, b) for _, s, b, _, _ in env._ability_pending}
        for button, cid, uid in commands:
            if owner == side and env.names[cid] == 'IceWizard' and (owner, button) not in pending:
                recorder.counts['iw_scheduled'] += 1
                pending.add((owner, button))
        return queue(owner, commands, delay)

    env.core.step, env.eng.act, env.queue_abilities = observed_step, observed_act, observed_queue
    def restore():
        env.core.step, env.eng.act, env.queue_abilities = step, act, queue
    return recorder, restore
