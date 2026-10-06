# Saved-output inspection after original failure

Original CUDA collection remains FAILED, preserved in commit a196408. Both
1024-row blind output caches and the sample are present. No hand-enabled outputs,
independent check or complete collection report exist. Original source/receipts
are unchanged; this inspection does not reclassify the failed exact control.

Saved blind full-versus-censored inequalities / maximum finite absolute difference:
gate2 /2.384185791015625e-7; card6 /1.9073486328125e-6;
wait13 /1.1920928955078125e-6; value7 /4.76837158203125e-7;
cell2492 /4.76837158203125e-6; global181 /4.76837158203125e-7.
All head argmax choices are unchanged. These measured small differences do not
identify the numerical cause. The collector had checked weight identity before
its failed assertion but did not persist the complete post-check report or base
input hashes; those absent records must not be claimed as retained proof.

Source review found the same model disables hand features before encoding, and
original augmentation clones mirrored arrays. A separately registered CPU,
single-threaded deterministic successor can test the same question with an exact
negative control; no tolerance waiver, unchanged CUDA retry or old-cache rescue.
Additionally, explicit float64 operand conversion is required for prospective
delta reductions: a float64 NumPy out array alone need not force float64 arithmetic.
This latent reduction issue was found by code review, not the cause of this failure.
