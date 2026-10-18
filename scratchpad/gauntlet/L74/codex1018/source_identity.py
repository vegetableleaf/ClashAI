"""Hash an explicit public SIM evaluation allowlist; emit no private acquisition data."""
import hashlib,json,pathlib
P=pathlib.Path
cb=next(p for p in (P('/workspace/cb_combo'),P('/workspace/c3/cb'),P('/workspace/codex1018/cb')) if p.is_dir())
names=[
 'pipeline/search_s0.py','pipeline/e1_eval.py','pipeline/decision_options.py',
 'pipeline/ability_head.py','pipeline/model_gen.py','pipeline/model_v3.py',
 'pipeline/dataset.py','pipeline/vocab.py','pipeline/e1_pool.py','pipeline/e1_view.py',
 'pipeline/obs_contract.py','pipeline/own_ability.py','pipeline/spell_value.py',
 'pipeline/royale_runtime.py','pipeline/royale_env.py','pipeline/royale_heroiw.py',
 'scratchpad/gauntlet/L74/gap/gap.py','scratchpad/gauntlet/L74/livecal/livecal.py',
 'scratchpad/gauntlet/L74/livecal/live_truth.py',
 'scratchpad/gauntlet/L74/troops/build_manifest_fork36.json',
 'scratchpad/gauntlet/L74/mix/decks_live_eval.json']
print(json.dumps({n:hashlib.sha256((cb/n).read_bytes()).hexdigest() if (cb/n).is_file() else None for n in names}))
