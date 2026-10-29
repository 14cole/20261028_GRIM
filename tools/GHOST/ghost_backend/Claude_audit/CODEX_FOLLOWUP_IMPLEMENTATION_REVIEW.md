# Follow-up implementation for Claude review

The requested follow-ups are implemented and qualified in the [new package](../Codex_audit/followups_20261029/README.md). The starting commit is `bb25908`; this package records the subsequent follow-up work.

Implemented: a request-owned, memory-admitted tighter-inverse preference with rejection recovery; condition-probe labels; paired native/regional fallback evidence; exclusive worker acquisition and cleanup; batch-count notices without a floor; clearer refusal context; correct batch propagation through reference-mesh fallback; explicit forecast scope and complex-medium diagnostics; bounded Windows snapshot-publication retries; and the headless UTF-8 log contract.

The serial inlet comparison improved from 43.16 to 38.40 seconds, with matching fields and unchanged gates. New 15 GHz metal-inlet trials passed with 3.97 and 4.75 GiB peak RSS under an 8 GiB solve budget, below the user's 32 GB ceiling. One used dense throughout; the narrower example switched to compressed after refinement.

Controlled loss experiments support investigating attenuation-aware forecasts, but do not justify reducing admission estimates yet. A leaf-size experiment saved RAM while slowing the solve. A bounded reciprocal whole-query cache had no hits and was not promoted to production. See the raw evidence and explicit limitations in the package.

Please review hint compatibility, payload/headroom accounting, one-time fallback after hinted solve rejection, pool lease ownership, paired rank-versus-storage fallback, snapshot retry cleanup/no-overwrite behavior, and reference-mesh batch propagation. Source snapshots, a patch, hashes and timestamped validation reports are provided.

Validation: 223 unique regression tests pass by latest saved outcome, with five certified end-to-end trials and six refined loss experiments. Development failures and their successful reruns remain in the package.
