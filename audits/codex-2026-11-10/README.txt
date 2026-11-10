Independent correctness review of Claude's implementation

Start with IMPLEMENTATION_REVIEW.txt, then coverage.csv.
All 191 supplied checks pass, but independent tests identify four requested
changes: memory/BLAS deadlock, uncaught worker failure during submission,
coarse BOR kernel publication outside tolerance, and mislabeled quadrature
calibration orders.

The ZIP contains reproduction scripts, raw evidence, and pinned source.
Extract it and follow its README.txt to rerun the checks.

Reviewed Claude commit: 1a6addedc89c8e6f9cd52b7e5aaa098a8962dcdb
This branch starts at that reviewed commit and adds only review artifacts.

ZIP SHA-256:
0b93f18cf30afd5b13b2c2759d40f1b398b023e9f6a46cd7a0d27e47bb5f2334

The artifacts are preserved as delivered. Their statement that no GitHub
changes were made describes the review before this subsequent publication.
