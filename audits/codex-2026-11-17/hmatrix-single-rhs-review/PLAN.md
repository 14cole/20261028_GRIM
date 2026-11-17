# Review and validation plan

Pinned Claude 198bbf500072f702c8d877558e7c64ecf9a8f24c. Read the report,
independent plan and single_column_layout.py before writing this plan.

1. Verify pinned reviewer text/JSON records; independently replay 40 RAM
   bisection outcomes and batch widths. These are ledger limits, not OS pressure.
2. Run the reviewer layout script unchanged against parent production,
   integrated production and a research-only Fortran-E conversion. Save full
   arrays and assert the comparisons; do not treat print-only results as tests.
3. Independently extend to a second geometry, normal/transpose/adjoint refined
   solves, physical and random RHS, width one/two/many, and Dense reference
   coefficients. Check complete solutions, residuals and fields as applicable.
   No timing claim is planned; no production-layout change is presumed needed.
4. Narrow bit-identity claims to observed configurations. Decide explicitly
   whether restoring old layout is justified by accuracy, cost and task goals.
5. Publish report and complete fresh evidence on a new audit branch, preserving
   production unless a correctness failure warrants a separately validated fix.
