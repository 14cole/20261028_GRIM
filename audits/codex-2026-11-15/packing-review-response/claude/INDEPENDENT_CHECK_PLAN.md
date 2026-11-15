# Independent check plan (written before running any check)

Written after reading Codex's handoff `HANDOFF_DENSE_COMPRESSED_RESEARCH.md`
(4e0d6e0) once, before opening its scripts, JSON or evidence. Not blind to its
conclusions; independent in method.

## Hypotheses and acceptance criteria

1. Inverse packing (complex64 `v12,v21,e1,e2`).
   - H: it cuts retained inverse bytes by roughly 40% but process peak by well
     under 10% at 32k, because the peak is set by the operator and assembly.
   - H: it costs extra refinement steps, more so on ill-conditioned cases,
     because the inverse tree already loses about five digits (my leaf
     condition numbers of 1e6-1e7 last round); single precision factors leave
     little margin. Prediction: on a high-contrast low-loss multilayer the
     packed inverse needs clearly more refinement, or fails its gate.
   - Accept "not default" if peak saving < 10% and solve time rises. Accept
     "useful memory-pressure option" only if a budget that rejects the baseline
     admits the packed build AND every production gate still passes.
   - Accuracy: packed vs fresh Dense on a harder case, both polarizations:
     density 1e-7, field 1e-8 (Codex's limits), production gates unchanged.
2. F-order output for the Dense residual product.
   - H: the gain comes from memory layout of the product output/RHS for narrow
     batches (numpy choosing a slower path when the result is C-order), so it
     should reproduce on a synthetic matrix with no solver at all, and should
     shrink for wide batches.
   - Accept as a candidate only if (a) a standalone microbenchmark written
     independently shows the effect at 16 columns with alternating order,
     (b) products are equal to roundoff, (c) paired whole-solve repeats on my
     host show a gain larger than the run-to-run spread. Reject if (c) fails.
3. Persistent C-order coefficients: expect no advantage over 2 once the copy is
   counted. Check only by microbenchmark.
4. Batching: narrow batches save RAM proportional to batch width x n and cost
   time; RHS compression should not matter when no columns are dropped.
5. Operator dominates Compressed memory at 32k: check from my own earlier
   32k Compressed stage records, not Codex's.

## Planned fresh work

- Own microbenchmark of the product (synthetic complex matrix).
- Paired, order-alternated whole-solve repeats of control vs F-output.
- 32k Compressed baseline vs packed on my host (peak, refinement, accuracy
  against my saved 32k reference density).
- Packed vs unpacked vs fresh Dense on a harder multilayer of my own choosing
  (higher contrast, lower loss than Codex's), TE and TM.
- A storage-budget test: does packing turn a rejected build into an accepted
  one?
- Replay of Codex's evidence archive.

Not planned this round: disk pressure, nested bases, out-of-core LU.
