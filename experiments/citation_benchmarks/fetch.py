#!/usr/bin/env python3
"""Fetch pinned external citation benchmarks without vendoring their data."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import tarfile
import urllib.request
from pathlib import Path

SCICITE_URL = "https://s3-us-west-2.amazonaws.com/ai2-s2-research/scicite/scicite.tar.gz"
SCICITE_SHA256 = "711ece2c4e61d116c8ae5bb07e9fbb2ee9ff7bba004b4cab7fbd0ac3af499193"
CORWA_URL = "https://github.com/jacklxc/CORWA.git"
CORWA_COMMIT = "db034d9da472ff049c73ade21de2d5439b10207a"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    archive = args.output / "scicite.tar.gz"
    if not archive.exists():
        urllib.request.urlretrieve(SCICITE_URL, archive)
    actual = checksum(archive)
    if actual != SCICITE_SHA256:
        raise RuntimeError(f"SciCite checksum mismatch: {actual}")
    target = args.output / "scicite"
    if not target.exists():
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(args.output, filter="data")

    corwa = args.output / "CORWA"
    if not corwa.exists():
        subprocess.run(["git", "clone", CORWA_URL, str(corwa)], check=True)
    subprocess.run(["git", "-C", str(corwa), "checkout", CORWA_COMMIT], check=True)
    print("SciCite:", target)
    print("CORWA:", corwa, CORWA_COMMIT)


if __name__ == "__main__":
    main()

