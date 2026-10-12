# PRO2 — saved public replays, data only

Status: source conversion and no-SIM checks completed; pod execution pending.
No training code/configuration was edited. Nothing is wired into training or live
play. Changes are uncommitted. All work was offline.

## Current format chain (10 lines)

1. Saved RoyaleAPI `payload.html` contains 20 Hz command markers, timeline ability flags and public card summaries; `phase_stats.ReplayHTML` parses the commands.
2. Historical RoyaleAPI crawls and FirstLight `tools/hf_to_crawl.py` produce `battles.csv`, `plays_ext.csv`, and `tags.json` (crawl2 format).
3. `battles.csv` supplies both comma-separated decks and crowns; `plays_ext.csv` supplies tick, play index, card, side, ability and millitile coordinates.
4. `research/sandbox_tools/replay_drive.load_battle` maps red→0/blue→1 and rotates seat `attr_i=1` by `(18000-x,32000-y)` exactly once.
5. `replay_drive.drive` infers an opening deal, drives both command streams at level 11, and records acceptance, delays, crowns and deterministic hashes.
6. `replay_batch.py` built `corpus_gen_pilot/s0..s3`; subsequent ability/public re-drives produced `s0_public_v1..s3_public_v1` plus `corpus_v6/{hogeq,icebow}_public_v1`.
7. Current public recordings contain `final_decks`, `expected`, `log`, pre-play `play_frames`, and full/native/public-object `frames` every 10 ticks, with abilities driven.
8. `pipeline.dataset.build_replay` uses those simulated states for accepted PLAY rows and WAIT rows, own-frame coordinates, own history, hand and real result labels.
9. `pipeline.dataset_gen` applies card identities, exact observed forms, public-only opponent observations, projectile/effect features and fv5 body identity; it dedupes replay filenames.
10. `L73/gen_v32/build.sh` builds `icebow/data/pipeline/gen_dataset_v32_fv5.npz`: fv5, lattice, wait stride 40, play window 20, shift 0, validation 10%; its metadata confirms 14,818 recordings/14,661 replay IDs across six corpora.

**Runtime distinction:** the current corpus was driven through the native game
engine, not RoyaleSim. The supplied pod builder uses the pinned RoyaleSim runtime
and the unchanged fv5 dataset builder. Its compact encoding is compatible, but
its reconstructed states are not verified equivalent to the native corpus.
`record_native=true` describes the required ID/compact encoding in this adapter;
`recording_origin=royalesim` and embedded `pro2_provenance` describe actual origin.

## Measured source conversion

`conversion_summary.json` is the reviewable aggregate; detailed sanitized source
artifacts are ignored under `output/`. The owner's original files were not copied.
Both directories contain JSON wrappers with `payload.html`; bait is nested under
`Downloads/bait/bait/` and is discovered recursively.

- 1,083 files: raw2 848, bait 235; no parse errors.
- 1,069 unique new replays; 14 input duplicates; **0 existing battle-ID matches**.
- Existing index: 14,818 recording paths, 14,661 unique IDs. Time+deck keys cover
  2,403 existing source rows, but **none of the new pages supplies battle time**.
  Time+deck dedupe is implemented/tested but cannot establish additional overlap
  here. `captured_at` is never mistaken for battle time; anonymized HF IDs remain
  a possible unmeasured overlap.
- 1,064 crawl-ready replays; 5 quarantined for invalid/unpositioned commands or
  incomplete/ambiguous card-summary decks. All commands remain in sanitized JSONL.
- 83,733 card-play events and 3,613 ability events; 951 replays have abilities.
- Visible evo/hero suffixes: 0. Unmarked forms are **unknown**, not proven base.

Counts are **deck sides**, not matches, and include quarantined sources:

| Type | All new sides | Crawl-ready sides |
|---|---:|---:|
| Icebow-like (at least 5 of the specified 8 cards) | 48 | 48 |
| Other X-Bow | 7 | 7 |
| Log Bait | 379 | 379 |
| Other | 1,704 | 1,694 |

Log Bait operational definition: Goblin Barrel plus at least one of Princess,
Goblin Gang, Dart Goblin or Skeleton Barrel, after the two X-Bow categories.
Deck summaries disclose seen cards, not necessarily unplayed slots or forms.

| Phase | All source card plays | Crawl-ready card plays | Dataset rows |
|---|---:|---:|---|
| 1x, ticks [0,2400) | 29,344 | 29,216 | pending SIM |
| 2x, ticks [2400,4800) | 41,324 | 41,186 | pending SIM |
| 3x, ticks [4800,6000) | 13,045 | 12,999 | pending SIM |
| Postgame, ticks ≥6000 | 20 | 0 | pending SIM |

## Reproduce locally, no SIM

```powershell
python scratchpad/gauntlet/L74/pro2/convert.py --out scratchpad/gauntlet/L74/pro2/output/new_run
python scratchpad/gauntlet/L74/pro2/audit.py scratchpad/gauntlet/L74/pro2/output/new_run
icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/pro2/tests -q -p no:cacheprovider
```

The converter refuses nonempty output directories. `audit.py` recounts source and
CSV artifacts, verifies accounting and regenerates `conversion_summary.json`.
Tests use two tiny allowlisted real-page excerpts; original source SHA-256s and
the exact trimming procedure are in `tests/provenance.json`. Player identities
are omitted everywhere, including fixtures. No network calls or raw pages enter
the repository. `output/` and temporary test artifacts are ignored.

## Pod handoff (not executed)

Provision the repository, its public card catalogs, the already-installed pinned
Linux runtime, numpy and torch, and the sanitized `output/replays.jsonl` locally
on the pod. This script does not download/install or transfer anything. It stays
OFF without `--run`, and refuses unknown forms without the second explicit flag.

```bash
# From the repo root; explicitly accept exploratory base-form reconstruction:
bash scratchpad/gauntlet/L74/pro2/build_rows.sh --run --allow-unknown-forms
```

Default destination: `/workspace/results/PRO2/` (must be empty). Overrides:
`PRO2_SOURCE`, `PRO2_OUT`, `PRO2_PYTHON`; runtime defaults to
`ROYALE_RUNTIME=20261006-linux`. A bounded first check can use `--limit 10` and
`PRO2_OUT=/workspace/results/PRO2_smoke` so the full destination stays empty.

Only `build_rows.py:drive` needs SIM. It infers deals using the existing
`RoyalePoolEnv`, submits both sides' commands and attributable ability buttons,
records actual pre-act/periodic states, and retains refused/delayed plays. The
fv5 packing stage needs numpy/torch and catalogs, but no running SIM once the
recordings exist. No GPU is required. Planning estimate: **1–3 hours on one pod
CPU worker**, including packing, with substantial uncertainty; this is not a
measured benchmark. Use the first ten replay timings to revise it. Allow several
GB of disk/RAM for recordings, row arrays and the pipeline's disk spool.

Outputs on a successful build: `rows.npz`, `rows.json`, `summary.json`,
`SUMMARY.txt`, `DONE`, `row_fidelity.npz`, `replay_fidelity.json`, `failures.json`,
and `corpus/replay_*.json`. DONE says `EXPLORATORY_SIM_ROWS_UNVERIFIED_FOR_TRAINING`;
it never means native fidelity or model acceptance. Fatal failures create no DONE.
The NPZ carries origin/uncertainty metadata, and the sidecar indexes each row by
replay and tick. Summary includes actual 1x/2x/3x and per-deck row counts.

## Blockers and fidelity limits

- SIM execution is unavailable on this laptop sandbox. No new dataset rows or
  runtime divergence counts have been claimed. Shell execution/syntax checking
  also failed before Bash started (`CreateFileMapping`, Windows error 5).
- `minion-giant` is absent from the existing public card catalog: 209 deck sides,
  197 crawl-ready replays. Those replays fail explicitly; no alias is invented.
- 1,855 ability events in crawl-ready sources have no known champion or visible
  hero-form attribution. The runner refuses ambiguous presses, records the
  reason, and flags all subsequent rows in that replay as command-diverged.
- All deck forms are unobserved in the supplied pages. Exploratory runs assume
  base forms where unspecified and mark every row's forms unknown. A faithful
  native-equivalent reconstruction requires additional public deck/form evidence.
- Existing fidelity definitions (command acceptance, delays, final crowns and
  terminal timing) are retained. The existing
  `research/sandbox_tools/validate_public_capture.inspect` oracle is also run and
  its errors retained; missing native-specific exports are not fabricated.
- **Unit missing/out-of-place versus the original battle is unavailable:** pages
  have no body snapshots. The existing native capture oracle checks recorded
  identities/ability controllers/export consistency, not the absent original
  board. Row-side `body_fidelity_known=false` and summary nulls preserve this
  limitation. Command-divergence and outcome-mismatch masks are measured on pod;
  neither is presented as a unit-position comparison.
- The fv5 builder creates a new observed-card vocabulary. This isolated dataset
  is not automatically compatible with a checkpoint's vocab or authorized for
  merging into training. No training/config changes or uploads were performed.
