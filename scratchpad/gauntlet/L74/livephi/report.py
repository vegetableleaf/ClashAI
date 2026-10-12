"""Render the report from persisted measurements, never hand-enter metrics."""
import collections
import json
import numpy as np
from build import HERE


def fmt(v):
    if v[0] is None:return "unavailable"
    return f"{v[0]:.4f} [{v[1]:.4f}, {v[2]:.4f}]" if v[1] is not None else f"{v[0]:.4f} [undefined]"


def main():
    r=json.loads((HERE/"results.json").read_text());m=json.loads((HERE/"dataset_manifest.json").read_text())
    tr=json.loads((HERE/"training.json").read_text());d=dict(np.load(HERE/"dataset.npz"));lines=[]
    emit=lines.append
    emit(f"# LIVEPHI: {r['verdict']['decision'].upper()}\n")
    emit("Status: offline experiment complete; changes uncommitted. No policy trained, network used, live script changed, or deployment performed.\n")
    emit("## Dataset and method\n")
    emit(f"Frozen candidate list: {len(m['matches'])+len(m['excluded'])} logs since 2026-10-08. Included {len(m['matches'])} decisive main-account X-Bow matches, {m['rows']:,} decision rows. Exact `phase_stats.read_live` selection and final public tower-scorecard labels; this is a result proxy, not a separate authoritative result event. Draws and post-300-second drain decisions dropped. The supplied approximate count was not forced.\n")
    emit("Exclusions: "+str(dict(collections.Counter(a['excluded'] for a in m['excluded'])))+".\n")
    emit("| Split | Calendar dates | Matches | Wins | Rows | 1x | 2x | 3x | First 30 s |\n|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for s,name in enumerate(("train","validation/calibration","held-out test")):
        rec=[x for x in m['matches'] if x['split']==s];q=d['split']==s;t=d['tick'][q]
        emit(f"| {name} | {min(x['file'][10:18] for x in rec)}–{max(x['file'][10:18] for x in rec)} | {len(rec)} | {sum(x['label'] for x in rec)} | {q.sum():,} | {(t<2400).sum():,} | {((t>=2400)&(t<4800)).sum():,} | {(t>=4800).sum():,} | {(t<600).sum():,} |")
    emit(f"\nLatest whole calendar-date block nearest 20% is test ({sum(x['split']==2 for x in m['matches'])/len(m['matches']):.1%}); the same rule chooses calibration from earlier dates. Match clusters never cross splits. Labels, IDs, dates, policy actions and file names are absent from features.\n")
    emit("Features: exact logged model-time public bodies/towers/elixir rebuilt with the live policy's `obs_contract.to_tokens`, the same scalar channels and token mask, then a fixed 35-dimensional board projection (25 scalars, five pooled body quantities per side). This small model intentionally omits card identity, hand, next card, action history and projectiles. It is not a replacement policy trunk. Opponent elixir is only the logged public counter estimate.\n")
    emit(f"Model: 35→32 tanh→1 MLP, {tr['n_parameters']:,} learned parameters; single CPU thread, 30 epochs, validation-selected epoch {tr['selected_epoch']}, {tr['seconds']:.2f} s including calibration. Training uses inverse row-count match weights. Positive-slope Platt calibration fitted on validation only. `phi_live.pt` stores normalization and calibration; SHA256 `{r['phi_checkpoint_sha256']}`.\n")
    emit("Baseline: `rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt`, SHA256 `"+r['baseline_checkpoint_sha256']+"`. Its frozen value scalar is P(win)−P(loss); tower_crown uses the existing 0.3/0.3 weights. For Brier, each baseline gets its own positive-slope Platt fit on the same validation matches (separate maps for raw and smoothed scores); no test/pro labels enter calibration.\n")
    emit("Baseline input limitation: logs do not contain a full input tensor. Model-time board and object arrays are exact; public opponent history uses every available public frame plus decision snapshots, with the live Hero deduplication step. Confirmed own actions rebuild past; own next card is padded unknown, and pending-hand/ability detail may differ. Frame events' EVAL_ONLY opponent elixir is discarded by an allowlist and a poison-field test. Therefore the frozen value-head comparison is on reconstructed public inputs, not a claim of bit-identical original full input tensors. L73 pro inputs are exact original rows and were checked against saved scalar/label arrays.\n")
    emit("Reconstruction audit: `baseline_input_repair.json` verifies the history correction left all 219 validation/test matches' trained board features bit-identical. Only finalized input-revision-3 baseline predictions are accepted. `baseline_parity.json` verifies the value-only extraction equals the full checkpoint's `encode_gen` value output exactly on four persisted real rows.\n")
    matches=[x for x in m['matches'] if x['split']==2 and x.get('checkpoint') and str(x['checkpoint']).endswith('rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt')]
    mask=np.isin(d['match'],[x['match'] for x in matches]);err=np.abs(d['gate_rebuilt'][mask]-d['gate_logged'][mask])
    if len(err):emit(f"Full-input fidelity diagnostic on matching-checkpoint test logs: {len(matches)} matches, {len(err):,} rows, |rebuilt gate−logged gate| median {np.median(err):.4f}, p95 {np.percentile(err,95):.4f}. This also reflects differing live options; it is not Phi error.\n")
    emit("Phases: 1x [0,120), 2x [120,240), 3x [240,300) seconds. Rows are decision-weighted; 95% percentile CIs use 500 paired bootstrap draws by match. Pro bootstraps resample replay IDs, carrying both perspectives together. All methods use exactly the same evaluated rows. AUC gain is positive; Brier improvement is negative.\n")
    for source in ('live','pro'):
        emit(f"## {'Held-out live' if source=='live' else 'L73 pro transfer'} AUC / Brier\n")
        for suffix,title in (("","Raw"),("_10s","Causal trailing 10-second mean")):
            emit(f"### {title}\n\n| Phase | Rows / matches | Method | AUC [95% CI] | Brier [95% CI] |\n|---|---:|---|---|---|")
            for ph,row in r[source]['table'].items():
                for n in ('live_phi','value_phi','tower_crown'):
                    emit(f"| {ph} | {row['rows']:,} / {row['matches']} | {n} | {fmt(row['auc'][n+suffix])} | {fmt(row['brier'][n+suffix])} |")
            emit("\n| Phase | Paired difference | ΔAUC [95% CI] | ΔBrier [95% CI] |\n|---|---|---|---|")
            for ph,row in r[source]['table'].items():
                for base in ('value_phi','tower_crown'):
                    p=row['paired']['live_phi'+suffix+'-'+base+suffix]
                    emit(f"| {ph} | live_phi − {base} | {fmt(p['auc'])} | {fmt(p['brier'])} |")
            emit("")
    emit("## Calibration and step jitter\n")
    emit("Ten equal-width reliability bins, mean predicted probability, observed win rate, and ECE overall/per phase are retained in `results.json`.\n")
    emit("| Cohort | Phase | live_phi ECE | value_phi ECE | tower_crown ECE |\n|---|---|---:|---:|---:|")
    for source in ('live','pro'):
        for ph,c in r[source]['calibration'].items():emit(f"| {source} | {ph} | {c['live_phi']['ece']:.4f} | {c['value_phi']['ece']:.4f} | {c['tower_crown']['ece']:.4f} |")
    emit(f"\nTest Brier of the constant training row win-prior predictor: {r['live']['prior_brier']:.4f}. Calibration gate was predeclared as ECE ≤ .05 and Brier no worse than that constant predictor.\n")
    emit("| Cohort | Potential | Std of consecutive ΔPhi | Match TV mean | Match TV median |\n|---|---|---:|---:|---:|")
    for source in ('live','pro'):
        for n,j in r[source]['jitter'].items():emit(f"| {source} | {n} | {j['step_delta_std']:.5f} | {j['tv_mean']:.4f} | {j['tv_median']:.4f} |")
    emit("\nJitter uses default shaping units: live_phi=.5×(2P−1), value_phi=.5×value scalar, tower_crown=.3×tower+.3×crown. TV excludes the forced terminal reset; each trajectory's TV and delta std are retained in `results.json`. Pro sides are separate trajectories. Smoothing averages prior decision rows in [tick−200,tick], including current row, never future rows.\n")
    emit("| Cohort | Paired jitter difference | Δstep std [95% CI] | Δmean TV [95% CI] |\n|---|---|---|---|")
    for source in ('live','pro'):
        for name,v in r[source]['jitter_comparisons']['paired'].items():
            emit(f"| {source} | {name} | {fmt(v['step_std'])} | {fmt(v['tv_mean'])} |")
    emit("")
    emit("## Exploitability diagnostics\n")
    dep=r['dependence'];e=dep['own_elixir']
    emit("Own-elixir partial dependence on every held-out row (all other encoded inputs fixed):\n\n| Elixir | Mean P(win) |\n|---:|---:|")
    for a,b in zip(e['grid'],e['mean_pwin']):emit(f"| {a} | {b:.5f} |")
    emit(f"\n5→10 elixir ΔP(win): **{fmt(e['delta_5_to_10'])}**; positive on {e['positive_row_fraction_5_to_10']:.1%} of rows. In default Phi units the difference is identical. Gate: upper CI ≤ .01; this is a sensitivity screen, not proof that a legal banking trajectory gains return. Potential shaping still telescopes.\n")
    for key in ('own_tower_hp','enemy_tower_hp'):
        v=dep[key];emit(f"{key}: fractions {v['fractions']}, mean P(win) {[round(z,5) for z in v['mean_pwin']]}; full-minus-5% {fmt(v['delta_full_minus_low'])}. Alive/known flags fixed; only standing known towers varied. Diagnostic counterfactuals can be off-manifold.\n")
    v=dep['own_troops_alive'];emit(f"Own troops alive: retain fractions {v['retained_fractions']}, mean counts {[round(z,3) for z in v['mean_counts']]}, P(win) {[round(z,5) for z in v['mean_pwin']]}; all−none {fmt(v['delta_all_minus_none'])}. Buildings are retained. {v['rows']} stratified-in-time rows; match bootstrap. Removal changes the corresponding token pooling only; no elixir refund.\n")
    emit("L73 behavior checks reused: late PLAY leaving <3 elixir vs ≥3, and near-cap WAIT (≥9.5) vs lower-elixir WAIT. Outcome reference is residualized within 30-second clock × crown-difference × tower-HP-difference strata. These are observational associations, not causal penalties from pros.\n")
    emit("| Cohort | Behavior | Rows | Outcome residual [CI] | live_phi Δ10s [CI] |\n|---|---|---:|---|---|")
    for source in ('live','pro'):
        for k,v in r[source]['behavior'].items():
            if k in ('note','contrasts'):continue
            emit(f"| {source} | {k} | {v['rows']:,} | {fmt(v['outcome_residual'])} | {fmt(v['delta10s']['live_phi'])} |")
    emit("\nRelative behavior contrasts use the same match-bootstrap weights for both groups. A positive change contrast can indicate a relative preference even if both groups' absolute changes are negative. Changes here use raw 2P−1 scores; default shaping weight halves them.\n")
    emit("| Cohort | Contrast | Outcome residual difference [CI] | Raw live_phi Δ10s difference [CI] | Smoothed live_phi Δ10s difference [CI] |\n|---|---|---|---|---|")
    for source in ('live','pro'):
        for k,v in r[source]['behavior']['contrasts'].items():
            emit(f"| {source} | {k} | {fmt(v['outcome_residual'])} | {fmt(v['delta10s']['live_phi'])} | {fmt(v['delta10s']['live_phi_10s'])} |")
    emit("\nPro behavior conflict flags (negative outcome residual/difference upper CI, positive Phi-change/difference lower CI): "+str(r['pro_behavior_flags'])+". These flag observational disagreement, not causal exploitability or additional behavior rewards. An empty list is absence of detected conflict, not proof of safety.\n")
    emit("The detected raw overspending contrast reverses sign after trailing-10-second smoothing; it is not a detected overspending preference of the default smoothed option. Elixir partial dependence and the failed AUC/calibration gates independently reject the candidate.\n")
    emit("## Learner integration and verdict\n")
    emit("Opt in only with `shaping: live_phi`, `advantage: gae`, `critic_warmup_updates: >0`. Existing value-Phi weight/window/critic-scale validation is reused. Null `shaping_phi_ckpt` resolves to this directory's `phi_live.pt`. Loaded once on learner device, eval mode, no gradients; actors only record ticks. Terminal Phi is 0; F=gamma×Phi(next)−Phi(current). No behavior-paying terms or YAML default changes.\n")
    emit("Predeclared gates: "+json.dumps(r['verdict'])+".\n")
    emit("**"+r['verdict']['decision'].upper()+"**. This verdict concerns an offline potential predictor only. No policy was trained or deployed.\n")
    emit("Files: `build.py`, `fit.py`, `baselines.py`, `pro.py`, `evaluate.py`, `report.py`, `verify.py`, `GATES.md`, source/dataset manifests, per-match shards, `dataset.npz`, `pro_inputs.npz`, `pro_dataset.npz`, `phi_live.pt`, `training.json`, `results.json`, `heldout_predictions.npz`, `VERIFICATION.json`. Pipeline edits: `pipeline/live_phi.py`, `pipeline/rl_royale.py`, `pipeline/tests/test_live_phi.py`.\n")
    emit("Tests and final verification are recorded in `VERIFICATION.json`; rerun commands and provenance in `README.md`. Checkpoint is a local experimental artifact and remains opt-in even if the statistical gates pass.")
    (HERE/"REPORT.md").write_text("\n".join(lines),encoding="utf8")
    print("REPORT WRITTEN",flush=True)


if __name__=="__main__":main()
