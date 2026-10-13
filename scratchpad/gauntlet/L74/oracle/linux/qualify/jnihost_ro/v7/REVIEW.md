# ORACLE v7 review: implementation verified; runtime outstanding

No v7 Android attempt was made in this Windows session. No network, credentials,
client launch, patch, target memory write, GCP connection or commit was used.
The isolated Linux worker is unavailable under the current no-network boundary.

| Review field | Current evidence |
|---|---|
| Prior v6 stage reached | `jni_on_load`; retained successful receipt revalidated against its output hashes with the unchanged v6 reviewer. |
| v7 stage reached | None; target not executed. |
| v7 blocking stage | Unknown; no runtime attempt. Execution-environment access is the current work blocker. |
| Actual presentation sites attributed | None. No native failure has been observed in v7. |
| Patch application / qualification | Zero / zero. |
| Offline implementation | Both DEX files and observer compile; current source/artifact hashes checked; private runtime binding stays ignored. |
| Tests | See `VERIFICATION.json` for final counts and recorded checks. Synthetic receipts and mocked worker collection do not prove native callability. |

The dispatcher covers the requested lifecycle through manager update. Its
default ceiling is the v6 load-only boundary. A stage-limit switch is not a
resume switch: each authorized attempt starts a fresh process and can never
continue after the first failure. The runbook selects the final ceiling before
the single launch; no escalation ladder or automatic fallback is provided.

Two source-derived limitations are particularly relevant to interpreting that
attempt. First, the upstream Activity/resource/singleton bootstrap cannot be
copied under this ticket's boundary or from the incomplete target binding;
CreateGameMain receives a real AssetManager and null Activity, and missing
native receivers stop the chain. Second, no live Location-row selection recipe
exists in the supplied binding. Map calls are implemented, but the default
configuration will stop at that prerequisite if earlier stages succeed. A
recipe must be independently evidenced and supplied before the attempt; no
captured heap address or fabricated object is substituted.

Neither limitation establishes a presentation patch requirement. Candidate
sites remain the retained v3/v4 renderer/resource/loading/Home groups. The
reviewer lists them separately from actual receipt-backed attribution. A
generic crash, timeout or missing object stays unclassified/blocked; an
explicit libg refusal receives outcome (b) only with preserved causal evidence.

Required handoff: run the README's shell syntax check and one staged attempt
on the already isolated Linux worker; preserve its first-stop receipts; run
the v7 reviewer. Attribute specific sites only where the diagnostic or stack
supports that correspondence. Do not retry, patch, spoof, start the client or
lower a prerequisite to manufacture later-stage evidence.
