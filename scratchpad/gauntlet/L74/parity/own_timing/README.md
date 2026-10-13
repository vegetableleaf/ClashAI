# OWN_TIMING

Offline analysis of own-troop PARITY divergence. Results and reading: [FINDING.md](FINDING.md).

Each script takes the PARITY fixed-rerun `new/` directory and prints its table (`queue_direct.py` also takes the
matching `sources/` directory):

```bash
python own_early.py    <new_dir>              # error vs time since the tap, buildings vs troops
python onset_speed.py  <new_dir>              # motion onset and speed, forward-walking troops
python queue_split.py  <new_dir>              # error vs tap->confirm gap
python queue_direct.py <new_dir> <sources_dir> # onset gap vs elixir at the tap
python time_align.py   <new_dir>              # best per-unit time shift and residual error
```
