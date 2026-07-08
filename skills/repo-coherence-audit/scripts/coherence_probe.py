#!/usr/bin/env python3
"""
coherence_probe — reúne, de una sola pasada, los HECHOS verificables de un repo
para auditar coherencia de documentación. No arregla nada: mide y reporta la
fuente de verdad, para que el agente compare contra lo que los docs afirman.

Uso:
    python coherence_probe.py [ruta-repo]   # por defecto: cwd

Salida: texto legible con versiones (todos los manifests), workflows (lista +
conteo), conteo de tests (best-effort por stack) y pins de acciones a SHA.
Cada bloque degrada silenciosamente si no aplica al stack. Solo stdlib.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

# Salida UTF-8 aunque la consola sea cp1252 (Windows) — evita mojibake.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # py3.7+
except (AttributeError, ValueError):  # pragma: no cover
    pass

# Directorios que nunca son "el repo": vendor, build y — clave — copias de
# trabajo (git worktrees bajo .claude/worktrees) que ensuciarían el drift con
# versiones viejas que no son la fuente de verdad.
_VENDOR = {"node_modules", "target", "dist", "build", "site-packages", "__pycache__"}


def _skip(p: Path, root: Path) -> bool:
    """True si la ruta cae en un directorio oculto (.git, .claude, .venv, …)
    o vendor. Nota: los workflows se leen aparte, no por rglob, así que
    excluir dirs ocultos aquí no afecta a .github."""
    for part in p.relative_to(root).parts[:-1]:
        if part in _VENDOR or (part.startswith(".") and part != "."):
            return True
    return False


def rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


def find_versions(root: Path) -> list[tuple[str, str]]:
    """Devuelve (fichero, versión) para cada manifest/marcador de versión."""
    out: list[tuple[str, str]] = []

    # package.json (raíz y sub-paquetes)
    for pkg in root.rglob("package.json"):
        if _skip(pkg, root):
            continue
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "version" in data:
                out.append((rel(root, pkg), str(data["version"])))
        except (json.JSONDecodeError, OSError):
            pass

    # pyproject.toml
    for pp in root.rglob("pyproject.toml"):
        if _skip(pp, root):
            continue
        try:
            text = pp.read_text(encoding="utf-8")
        except OSError:
            continue
        ver = None
        if tomllib:
            try:
                d = tomllib.loads(text)
                ver = (d.get("project", {}) or {}).get("version") or (
                    d.get("tool", {}).get("poetry", {}) or {}
                ).get("version")
            except Exception:
                ver = None
        if not ver:
            m = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', text)
            ver = m.group(1) if m else None
        if ver:
            out.append((rel(root, pp), ver))

    # Cargo.toml
    for cg in root.rglob("Cargo.toml"):
        if _skip(cg, root):
            continue
        try:
            m = re.search(
                r'(?ms)^\[package\].*?^\s*version\s*=\s*"([^"]+)"',
                cg.read_text(encoding="utf-8"),
            )
            if m:
                out.append((rel(root, cg), m.group(1)))
        except OSError:
            pass

    # VERSION / version.txt
    for name in ("VERSION", "version.txt"):
        f = root / name
        if f.is_file():
            try:
                v = f.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                if v:
                    out.append((name, v))
            except OSError:
                pass

    # __version__ en Python
    for py in root.rglob("__init__.py"):
        if _skip(py, root):
            continue
        try:
            m = re.search(
                r'''(?m)^__version__\s*=\s*["']([^"']+)["']''',
                py.read_text(encoding="utf-8"),
            )
            if m:
                out.append((rel(root, py), m.group(1)))
        except OSError:
            pass

    return out


def find_workflows(root: Path) -> list[str]:
    wfdir = root / ".github" / "workflows"
    if not wfdir.is_dir():
        return []
    files = sorted(
        p.name for p in wfdir.iterdir()
        if p.suffix in (".yml", ".yaml") and p.is_file()
    )
    return files


def count_tests(root: Path) -> list[str]:
    """Best-effort. Prueba pytest --collect-only en la raíz y en backend/."""
    notes: list[str] = []
    candidates = [root]
    for sub in ("backend", "server", "api", "src"):
        d = root / sub
        if (d / "pyproject.toml").is_file() or (d / "tests").is_dir():
            candidates.append(d)
    seen = set()
    for d in candidates:
        if d in seen:
            continue
        seen.add(d)
        if not (d / "tests").is_dir() and not list(d.glob("test_*.py")):
            continue
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                cwd=d, capture_output=True, text=True, timeout=180,
            )
            m = re.search(r"(\d+)\s+tests?\s+collected", r.stdout + r.stderr)
            if m:
                notes.append(f"{rel(root, d)}: {m.group(1)} tests (pytest --collect-only)")
            elif r.returncode != 0:
                notes.append(f"{rel(root, d)}: pytest no ejecutó (¿deps sin instalar?)")
        except (subprocess.TimeoutExpired, OSError):
            notes.append(f"{rel(root, d)}: pytest no disponible")
    return notes


def find_pinned_actions(root: Path) -> list[str]:
    wfdir = root / ".github" / "workflows"
    if not wfdir.is_dir():
        return []
    pat = re.compile(r"uses:\s*([^\s@]+@[0-9a-f]{40})\s*(#\s*\S+)?")
    found: dict[str, str] = {}
    for wf in wfdir.iterdir():
        if wf.suffix not in (".yml", ".yaml"):
            continue
        try:
            for line in wf.read_text(encoding="utf-8").splitlines():
                m = pat.search(line)
                if m:
                    ref, comment = m.group(1), (m.group(2) or "").strip()
                    found[ref] = comment
        except OSError:
            pass
    return [f"{ref}  {c}".rstrip() for ref, c in sorted(found.items())]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"# coherence probe — {root}\n")

    print("## Versiones declaradas (fuente de verdad = manifest canónico)")
    versions = find_versions(root)
    if versions:
        for f, v in versions:
            print(f"  {v:<12} {f}")
        distinct = sorted({v for _, v in versions})
        if len(distinct) > 1:
            print(f"  !! DRIFT: conviven versiones distintas: {', '.join(distinct)}")
        else:
            print("  OK: todos los manifests coinciden.")
    else:
        print("  (sin manifests de versión detectados)")

    print("\n## Workflows en .github/workflows/")
    wfs = find_workflows(root)
    if wfs:
        print(f"  conteo real = {len(wfs)}")
        for w in wfs:
            print(f"    - {w}")
        print("  (recuerda: dependabot.yml NO es un workflow; jobs != workflows)")
    else:
        print("  (ninguno)")

    print("\n## Conteo de tests (fuente de verdad, no el README)")
    tests = count_tests(root)
    for t in (tests or ["  (no se pudo determinar automáticamente)"]):
        print(f"  {t}" if not t.startswith("  ") else t)

    print("\n## Acciones pinneadas a SHA (uses: reales)")
    pins = find_pinned_actions(root)
    if pins:
        for p in pins:
            print(f"  {p}")
    else:
        print("  (sin acciones pinneadas o sin workflows)")

    print("\n---\nAhora compara CADA número/afirmación de los docs contra esto.")
    print("Sincroniza solo los marcadores de estado ACTUAL; conserva lo histórico.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
