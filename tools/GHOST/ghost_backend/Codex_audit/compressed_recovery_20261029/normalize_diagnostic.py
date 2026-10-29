"""Publish a corrected diagnostic derivative without rewriting hashed evidence."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))
from ghost_backend.execution.diagnostics import mark_uncertified


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior = ROOT / 'Codex_audit/automatic_selection_20261029'
    evidence = json.loads((prior/'evidence_hashes.json').read_text())
    for item in evidence:
        assert sha(prior/item['path']) == item['sha256'], item['path']
    source = prior/'runs/coated3_condition_diagnostic/metadata.json'
    gates = source.with_name('original_quality_gates.json')
    source_hash, gates_hash = sha(source), sha(gates)
    normalized = mark_uncertified(json.loads(source.read_text()), dict(condition_est_max=1e99))
    normalized['diagnostic_provenance'] = dict(
        source=str(source.relative_to(ROOT)).replace('\\', '/'), source_sha256=source_hash,
        original_quality_gates=str(gates.relative_to(ROOT)).replace('\\', '/'), original_quality_gates_sha256=gates_hash,
        correction='Certification labels only; original numerical measurements and hashed source are preserved.')
    target = HERE/'coated_diagnostic_metadata.corrected.json'
    target.write_text(json.dumps(normalized, indent=2), encoding='utf-8')
    assert sha(source) == source_hash and sha(gates) == gates_hash
    def verify(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('passed', 'mesh_convergence_certified'):
                    assert child is False, key
                verify(child)
        elif isinstance(value, list):
            for child in value:
                verify(child)
    verify(normalized)
    manifest = dict(original_evidence_files_verified=len(evidence), original_evidence_unchanged=True,
        derivative=target.name, derivative_sha256=sha(target), source_sha256=source_hash,
        production_quality_passed=normalized['quality_gate']['passed'],
        production_mesh_certified=normalized['mesh_convergence_certified'],
        diagnostic_only=normalized['diagnostic_only'])
    (HERE/'diagnostic_derivative_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
