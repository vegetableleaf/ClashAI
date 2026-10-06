"""Draft only after reviewed final evidence; sending is a separate explicit step."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent/'learning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    assert not (HERE/'message.md').exists()
    e=read(HERE/'reviewed_evidence.json');r=read(HERE/'results_verified.json');assert e['complete'] and r['complete']
    names=['r1e_corrected','ordinary_v5','hand_blind_control_v5','hand_belief_v5']
    labels=['R1e','ordinary v5','blind control','hand model'];counts=r['counts']
    def line(group,field):
        n=counts[names[0]][group]['rows']
        return ', '.join(f'{label} {counts[name][group][field]}' for name,label in zip(names,labels))+f' (out of {n})'
    def delta(control,group,field):
        return (counts['hand_belief_v5'][group][field]-counts[control][group][field])*100/counts[control][group]['rows']
    lines=['**October 6: Public hand estimates and learned card retention**','',
        '**Work completed**',
        'Built a public opponent-hand representation from memory-board play history, with unknown states, cycle bounds and conditional Mirror identification. Prepared and independently checked all 213,995 training and 54,723 development rows, keeping future response windows separate from model inputs.',
        'Trained two models from the same eligible ordinary v5 weights, each for exactly 1,000 updates of 128 draws. Both have identical added capacity and training settings; only the hand model receives the hand estimates. Original expert actions and losses are unchanged. No counter table, card reservation rule or holding reward was added.',
        'Qualified strict loading, original initial predictions, finite gradients, public-input privacy, future-event exclusion, resets and deterministic token ordering. Three earlier qualification failures remain documented; the corrected implementation passed. A separate opt-in live companion adds hand estimates to the public audit.',
        '', '**What we found**',
        'These are recorded-action agreement results on the same corrected observations. R1e here is not its original live-input evaluation. All four models use identical labels and scoring; the parent was already exposed to this broader data.',
        'Rocket aim within one tile: '+line('rocket','aim1')+'.',
        'Complete Rocket actions: '+line('rocket','action')+'.',
        'Late Rocket actions: '+line('rocket_late_overtime_clock','action')+'.']
    for control,label in [('ordinary_v5','ordinary v5'),('hand_blind_control_v5','blind control')]:
        lines.append(f"Hand-model gains against {label}: Rocket aim {delta(control,'rocket','aim1'):+.3f} percentage points; full Rocket {delta(control,'rocket','action'):+.3f}; late Rocket {delta(control,'rocket_late_overtime_clock','action'):+.3f}. The unchanged required gains are +5, +2 and +2 respectively.")
    lines+=['','Barrel responses (63 labels):']
    for name,label in zip(names,labels):
        v=counts[name]['barrel_pro'];lines.append(f"{label}: {v['log_correct']} correct-lane Logs, {v['log_wrong']} wrong-lane Logs, {v['log_not_fired']} not fired; {v['action']} complete expert actions.")
    for group,title in [('witch','Witch'),('night_witch','Night Witch'),('furnace','Furnace'),
                        ('defensive_sequence','Defense'),('phase_late_overtime_clock','Late-game actions')]:
        lines.append(title+': '+line(group,'action')+'.')
    lines.append('General card agreement (17,192 PLAY labels): '+', '.join(f"{label} {counts[name]['all']['card']}" for name,label in zip(names,labels))+'.')
    lines.append('Overall action agreement: '+line('all','action')+'.')
    for name,label in zip(names,labels):
        b=r['play_wait'][name]['all'];d=r['play_wait'][name]['defensive_sequence']
        lines.append(f"{label}: {b['play_success']} correct PLAY actions and {b['correct_wait']} correct WAIT actions; defense splits into {d['play_success']} PLAY and {d['correct_wait']} WAIT.")
    spending=read(ROOT/'icebow/data/bench/hand_belief_learning_20261006/response_spending.json')
    lines+=['','The descriptive available-and-retained response slice: '+line('retention_status_4','action')+'.']
    lines.append('Predicted spending of that later response card in this slice: '+', '.join(f"{label} {spending[name]['retention_status_4']['predicted_response_card_spends']}" for name,label in zip(names,labels))+'. This is not an optimal-holding score.')
    lines+=['','**What it means**',
        'The hand reader is useful but imperfect: on exposed past native re-drives, the Mirror-aware successor made 4,367 complete development estimates out of 10,424 queries; 4,253 were exact (97.39%). The earlier version had 4,245 correct of 4,354 (97.50%). Mirror inference added coverage but did not improve precision. Missed or delayed public play sightings remain possible; no hidden opponent state is used.',
        'Expert windows include Log before Barrel, Tesla before several win conditions and Rocket before Collector. However, selecting a card because it is actually used later strongly favors retention or cycling back. Windows overlap and are not independent successes. These descriptive sequences do not establish intention, physical counter value, profitable retention or improved win rate. No new simulator matches or assistant-started live games were run for the hand models.']
    lines+=['','**Decision**']
    for control,label in [('ordinary_v5','ordinary v5'),('hand_blind_control_v5','blind control')]:
        failed=[k.replace('_',' ') for k,v in r['filters'][control].items() if not v]
        lines.append('Failed requirements against '+label+': '+(', '.join(failed) if failed else 'none')+'.')
    lines.append(('The fixed development continuation passed. Further acceptance work is still required.' if r['continuation_passed'] else
                  'The hand model is REJECTED for continuation by this fixed trial. The blind arm is an experimental control, not a replacement. Other improvements cannot override failed requirements.')+
                 ' Neither model is accepted or deployed. All gameplay, physical, statistical, public-input and remaining final acceptance requirements stay in force.')
    lines+=['','**Next**',
        ('Register the next matched gameplay and physical retention tests before considering acceptance.' if r['continuation_passed'] else
         'Diagnose where the added hand information changes decisions before choosing another learning recipe. Preserve the fixed budget and original failures; do not continue rejected weights or retune thresholds.'),
        'Separately improve qualification of public play timing and Mirror event identity. Continue to evaluate holding by downstream defense/resources/wins, not by how often a card is saved.']
    for arm,label in zip(names[-2:],labels[-2:]):
        loss=r['loss_means'][arm];lines.append(f"Training loss for {label}, first versus last 256 updates: {loss['first256']['loss']:.4f} to {loss['last256']['loss']:.4f}. This is training loss, not fixed evaluation accuracy.")
    (HERE/'message.md').write_text('\n\n'.join(x for x in lines if x!='')+'\n',encoding='utf-8')
    print('HAND_LEARNING_REPORT_DRAFTED')
if __name__=='__main__':main()
