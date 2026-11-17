# Review plan

Pinned Claude 8f2ef3316c13ee4dd80337ad567ba107746dbd0e. Read the report,
reviewer script and raw results before this plan. No new lifecycle solve is
needed. The new operator identity claim merits two fresh assemblies.

1. Verify all five reviewer files by Git blob identity; compare the new tile
   swap hashes/tables with our previously preserved fresh partition experiment.
2. Independently assemble the 8192-unknown star at one and four workers, with
   BLAS pinned to one. Save a per-array manifest, dtype/shape/layout, byte
   accounting and actual coefficient-query thread allocations/tile choices.
3. Compare all retained-array hashes and reviewer aggregate fingerprints.
   Treat equal retained-array storage as evidence about the operator payload,
   not a proof about every Python object or every geometry/platform.
4. Publish a concise acceptance/next-work report without changing production or
   reopening the accepted lifecycle fix.
