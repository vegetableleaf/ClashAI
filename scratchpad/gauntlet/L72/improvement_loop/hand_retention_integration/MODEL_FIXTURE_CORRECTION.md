# Initial hand-model qualification fixture correction

Original check_model.py and l72-hand-model-qualified receipt/output are preserved.
The117.678612s process failed with KeyError x inside the existing opponent_past
encoder. The fabricated public play fixture lacked x,y,form; actual PublicObserver
records those fields. The failure occurred at the first live row call, after the
initial parent/head/loss, finite backward, roundtrip and malformed-state checks.
No complete qualification report was written, no optimizer or deployable weight
was produced. Do not relabel the original failed process as passed.

Separate check_model_v2.py supplies x=4.5,y=6.0,form=0 to both fabricated play
fixtures. It repeats the incomplete qualification as a corrected probe with a fresh
receipt, binds the original failure, and leaves the actual model/live companion,
real data, original tests, tolerances and acceptance floors unchanged.
