#!/usr/bin/env python3
"""
Every maintained package and test Python source file must be pure ASCII.

Local trial and scratch directories are not maintained package source.
They may contain temporary copies or generated experimental files.
They are excluded consistently with the package-layout copy boundary; live
production source, launchers and regression tests remain covered.

A UTF-8 source file that passes through a Windows editor, an FTP client in
text mode, or any tool that re-encodes on save comes out the other side in a
local codepage. The em dash this repo used in comments and error messages
becomes a lone 0x97 byte, which Python 3 rejects outright:

    SyntaxError: (unicode error) 'utf-8' codec can't decode byte 0x97
    in position 0: invalid start byte

The file is then unimportable on the machine it was copied to, and the error
points at a decorative character rather than at anything meaningful. Nothing
here needs non-ASCII -- the characters were box-drawing rules in comment
banners, em dashes in prose, and Greek letters in docstrings -- so the cheapest
fix is to not have any.

Data files are exempt: .geo and .csv inputs are read with an explicit encoding
and are the user's, not ours.

Usage:
    python tests/test_source_is_ascii.py
"""

import sys
import subprocess
import unicodedata
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def maintained_source(path):
    relative = path.relative_to(REPO)
    return relative.parts[0] not in {'trials', 'scratch'}


def main():
    offenders = []
    scanned = 0
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z", "--", "*.py"],
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        tracked = None  # Installed/source distributions need no Git executable.
    if tracked is not None and tracked.returncode == 0:
        paths = [
            REPO / raw.decode("utf-8")
            for raw in tracked.stdout.split(b"\0")
            if raw
        ]
    else:
        paths = [
            path for path in REPO.rglob("*.py")
            if not any(part in {".git", "__pycache__"} for part in path.parts)
        ]
    for path in sorted(paths):
        # A tracked file may be intentionally deleted in the current change.
        if not path.is_file() or not maintained_source(path):
            continue
        scanned += 1
        raw = path.read_bytes()
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), start=1):
                for column, char in enumerate(line):
                    if ord(char) > 127:
                        offenders.append((
                            path.relative_to(REPO), number, column,
                            char, unicodedata.name(char, "?"),
                        ))

    print(f"scanned {scanned} Python file(s)")
    if not offenders:
        print("all pure ASCII")
        return 0

    print(f"\n{len(offenders)} non-ASCII character(s):\n")
    for rel, number, column, char, name in offenders[:40]:
        try:
            cp1252 = f"0x{char.encode('cp1252').hex()}"
        except UnicodeEncodeError:
            cp1252 = "not representable"
        print(f"  {rel}:{number}:{column}  {ascii(char)}  U+{ord(char):04X}  "
              f"{name}  (cp1252 {cp1252})")
    if len(offenders) > 40:
        print(f"  ... and {len(offenders) - 40} more")
    print("\nReplace them with ASCII equivalents; see the module docstring.")
    return 1


class SourceEncodingTests(unittest.TestCase):
    def test_scope_preserves_production_and_tests_but_not_historical_evidence(self):
        for name in ('run_gui.py', 'geometry/material_columns.py', 'tests/test_run_controls.py',
                     'twod/trials/example.py'):
            self.assertTrue(maintained_source(REPO/name))
        for name in ('trials/old/source.py', 'scratch/copy.py'):
            self.assertFalse(maintained_source(REPO/name))

    def test_python_sources_are_ascii(self):
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    sys.exit(main())
