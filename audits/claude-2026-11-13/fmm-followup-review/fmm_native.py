"""Stub: the external FMM2D library is not available on this host. Only the reusable (cached) engine is exercised."""
def evaluate(*a, **k):
    raise RuntimeError('FMM2D native library not available in this review')
