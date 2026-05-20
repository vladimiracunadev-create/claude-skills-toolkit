#!/usr/bin/env python3
"""
yaml-control — Valida YAML y workflows GitHub Actions antes de push.

Tres capas:
1. Sintaxis YAML (yaml.safe_load)
2. actionlint (sólo .github/workflows/) — si está en PATH
3. Convenciones del repo:
   - actions con SHA pinneado (40 hex chars)
   - permisos explícitos a nivel workflow
   - fail-fast: false en matrices grandes

Trabaja siempre desde Path.cwd().

Exit 0 si OK (warnings permitidos), exit 1 si hay errores.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Forzar UTF-8 en stdout para Windows console (cp1252 default)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML no instalado. Ejecuta: pip install pyyaml")
    sys.exit(2)


REPO = Path.cwd()
SHA_PATTERN = re.compile(r"^[A-Za-z0-9_.\-/]+@[a-f0-9]{40}$")
ACTIONS_USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)\s*$")


# -------------------------------------------------------------------------
# Discovery
# -------------------------------------------------------------------------

def git_modified_yaml() -> list[Path]:
    """YAML modificados según git (staged + unstaged + untracked)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True, cwd=REPO,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    files = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if path.endswith((".yml", ".yaml")):
            p = REPO / path
            if p.is_file():
                files.append(p)
    return files


def all_yaml(repo: Path) -> list[Path]:
    """Todos los YAML del repo, excluyendo .git/, node_modules/, .venv/."""
    exclude = {".git", "node_modules", ".venv", "venv", ".pytest-tmp",
               "__pycache__", "dist", "build", ".claude", ".github_old"}
    files: list[Path] = []
    for p in repo.rglob("*.yml"):
        if not any(part in exclude for part in p.parts):
            files.append(p)
    for p in repo.rglob("*.yaml"):
        if not any(part in exclude for part in p.parts):
            files.append(p)
    return files


def only_workflows(files: list[Path]) -> list[Path]:
    return [f for f in files if ".github/workflows/" in f.as_posix()]


# -------------------------------------------------------------------------
# Validation layers
# -------------------------------------------------------------------------

def check_syntax(path: Path) -> list[str]:
    """Capa 1: sintaxis YAML."""
    errors: list[str] = []
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("BOM UTF-8 al inicio del archivo (causa errores en runners)")
    text = raw.decode("utf-8", errors="replace")
    if "\t" in text:
        # Tabs en sangría son ilegales; permitidos sólo dentro de strings entre comillas
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            if "\t" in indent:
                errors.append(f"línea {i}: tab character en indentación (usa espacios)")
                break
    try:
        list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        errors.append(f"YAML parse error: {exc}")
    return errors


def check_actionlint(path: Path) -> tuple[bool, list[str]]:
    """Capa 2: actionlint si está disponible. Retorna (ejecutado, errores)."""
    if shutil.which("actionlint") is None:
        return False, []
    try:
        result = subprocess.run(
            ["actionlint", "-no-color", str(path)],
            capture_output=True, text=True, cwd=REPO,
        )
    except Exception as exc:  # noqa: BLE001
        return True, [f"actionlint crashed: {exc}"]
    if result.returncode == 0:
        return True, []
    errs = [ln for ln in (result.stdout + result.stderr).splitlines() if ln.strip()]
    return True, errs


def check_conventions(path: Path) -> tuple[list[str], list[str]]:
    """Capa 3: convenciones del repo. Retorna (errores, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # 3.1 — actions sin SHA pinneado
    for i, line in enumerate(lines, start=1):
        m = ACTIONS_USES.match(line)
        if not m:
            continue
        ref = m.group(1)
        # Skip locals (./.github/actions/...) y docker:// references
        if ref.startswith("./") or "://" in ref:
            continue
        if not SHA_PATTERN.match(ref):
            warnings.append(f"línea {i}: action sin SHA pinneado → {ref}")

    # 3.2 — permisos explícitos
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict) and "jobs" in data:
        if "permissions" not in data:
            warnings.append("workflow sin `permissions:` a nivel root (default es read/write)")

        # 3.3 — fail-fast en matrices grandes
        for job_name, job in (data.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            strategy = job.get("strategy") or {}
            matrix = strategy.get("matrix") or {}
            # Conteo simple: si alguna clave de matrix es una lista de >5
            for key, value in matrix.items():
                if isinstance(value, list) and len(value) > 5:
                    if strategy.get("fail-fast", True):
                        warnings.append(
                            f"job `{job_name}`: matriz `{key}` con {len(value)} elementos "
                            f"sin `fail-fast: false`"
                        )
                    break

    return errors, warnings


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Valida YAML + workflows GHA.")
    parser.add_argument("--all", action="store_true",
                        help="Valida TODOS los .yml/.yaml del repo (no sólo modificados).")
    parser.add_argument("--workflows", action="store_true",
                        help="Sólo .github/workflows/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sólo reporta, no instala ni modifica nada.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.all:
        files = all_yaml(REPO)
    else:
        files = git_modified_yaml()
        if not files and args.verbose:
            print("Sin YAMLs modificados detectados. Usa --all para escanear todo.")

    if args.workflows:
        files = only_workflows(files)

    if not files:
        print("Nada que validar.")
        return 0

    has_actionlint = shutil.which("actionlint") is not None
    print(f"YAML control — repo: {REPO}")
    print(f"  scope: {len(files)} archivos")
    if not has_actionlint:
        print("  ⚠ actionlint no instalado — saltando capa 2 (schema workflows)")
    print()

    total_errors = 0
    total_warnings = 0

    for idx, path in enumerate(files, start=1):
        rel = path.relative_to(REPO).as_posix()
        is_workflow = ".github/workflows/" in rel
        print(f"[{idx}/{len(files)}] {rel}")

        # Capa 1
        syntax_errors = check_syntax(path)
        if syntax_errors:
            for e in syntax_errors:
                print(f"  ✗ sintaxis: {e}")
            total_errors += len(syntax_errors)
            print()
            continue
        if args.verbose:
            print("  ✓ sintaxis YAML")

        # Capa 2
        if is_workflow:
            ran, action_errors = check_actionlint(path)
            if ran:
                if action_errors:
                    for e in action_errors:
                        print(f"  ✗ actionlint: {e}")
                    total_errors += len(action_errors)
                elif args.verbose:
                    print("  ✓ actionlint")
        elif args.verbose:
            print("  - actionlint omitido (no es workflow)")

        # Capa 3
        if is_workflow:
            conv_errors, conv_warnings = check_conventions(path)
            for e in conv_errors:
                print(f"  ✗ convenciones: {e}")
            for w in conv_warnings:
                print(f"  ⚠ convenciones: {w}")
            total_errors += len(conv_errors)
            total_warnings += len(conv_warnings)
            if not conv_errors and not conv_warnings and args.verbose:
                print("  ✓ convenciones")
        elif args.verbose:
            print("  - convenciones omitidas (no es workflow)")
        print()

    print(f"Resumen: {total_warnings} warnings, {total_errors} errores.")
    if total_errors:
        return 1
    if total_warnings:
        print("OK con warnings — revisa antes de push.")
    else:
        print("OK para push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
