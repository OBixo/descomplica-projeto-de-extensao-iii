from __future__ import annotations

import shutil
import site
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: montar_runtime_offline.py <pasta_runtime>")
        return 2

    runtime_dir = Path(sys.argv[1]).resolve()
    site_packages = runtime_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    candidates = []
    if hasattr(site, "getsitepackages"):
        candidates.extend(site.getsitepackages())
    user_site = site.getusersitepackages()
    if user_site:
        candidates.append(user_site)

    unique_candidates = []
    seen = set()
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(Path(c))

    source_pkg = None
    source_meta = None

    for base in unique_candidates:
        pkg = base / "pypdf"
        meta = next(iter(base.glob("pypdf-*.dist-info")), None)
        if pkg.exists():
            source_pkg = pkg
            source_meta = meta
            break

    if not source_pkg:
        print("ERRO: pypdf nao encontrado no Python base.")
        return 3

    dest_pkg = site_packages / "pypdf"
    shutil.rmtree(dest_pkg, ignore_errors=True)
    shutil.copytree(source_pkg, dest_pkg)

    if source_meta:
        dest_meta = site_packages / source_meta.name
        shutil.rmtree(dest_meta, ignore_errors=True)
        shutil.copytree(source_meta, dest_meta)

    print(f"OK: pypdf copiado para {dest_pkg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
