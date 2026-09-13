# tools/

Repo-level command-line tools for the pro-replay (HuggingFace) data path. Run every command from the repo root
with the deck venv's Python (e.g. `icebow\.venv\Scripts\python.exe`). No paths are hard-coded: each tool finds the
repo from its own location. Default outputs go under the repo-root `data/` folder, which `.gitignore` excludes.

| Tool | What it does | Usage |
|---|---|---|
| `hf_download.py` | Downloads + sha256-checks the 52 replay parquet parts (825 MB) listed in `hf_manifest.json`; resumable, stdlib only. | `python tools\hf_download.py [--dry-run] [--dest data\hf]` |
| `hf_manifest.json` | File list (path, bytes, sha256) of the `VanguardX101/IL_Replay` dataset, read by `hf_download.py`. | -- |
| `hf_to_crawl.py` | Converts the parquet parts into a crawl2-shaped folder (battles.csv, plays_ext.csv, tags.json, dedupe_report.json) for one deck; dedupes against the deck's own crawl if present. | `python tools\hf_to_crawl.py icebow [--hf data\hf\replays] [--out data\hf_crawl\icebow]` |
| `build_degraded.py` | Builds a live-like "degraded" twin of an S1 dataset (same rows, every board state through `obs_contract.degrade`). | `python tools\build_degraded.py icebow --corpus <dir> --out <npz> [--seed 0]` |
| `merge_aug.py` | Merges a clean S1 dataset with its degraded twin's train rows (val stays clean). | `python tools\merge_aug.py --clean <npz> --degraded <npz> --out <npz>` |

Offline tests (no network, no engine): `icebow\.venv\Scripts\python.exe -m unittest tools.tests.test_tools`
