#!/usr/bin/env python3
"""
pre-commit-guard — orquestador de validación previa a `git commit`.

Detecta los archivos staged (`git diff --cached --name-only`), los
particiona por extensión, y encadena:
  [a] yaml-control  sobre los *.y*ml staged
  [b] md-lint-fix --dry-run sobre los *.md staged
  [c] python-lint-guard --parity-only sobre los *.py staged

Aborta al primer error (fail-fast). Reporta resumen unificado.

A diferencia de pre-push-guard, NO corre pytest ni invoca ruff — pre-commit
debe ser rápido (< 2s en el caso típico). Por eso python-lint-guard corre
aquí en modo --parity-only: comprueba que el gate de lint declarado exista
de verdad, sin analizar violaciones. Lo pesado queda para pre-push-guard.

Soporta --install-hook / --uninstall-hook (opt-in, nunca automático).

Trabaja sobre Path.cwd().
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

HOME_SKILLS = Path.home() / ".claude" / "skills"
YAML_CONTROL = HOME_SKILLS / "yaml-control" / "yaml_control.py"
MD_LINT_FIX = HOME_SKILLS / "md-lint-fix" / "fix-md-lint.py"
PY_LINT_GUARD = HOME_SKILLS / "python-lint-guard" / "python_lint_guard.py"


@dataclass
class StepResult:
    name: str
    files: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    ok: bool = True
    output: str = ""
    duration_s: float = 0.0


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace"
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError as exc:
        return 127, str(exc)


def is_git_repo(path: Path) -> bool:
    code, _ = run(["git", "rev-parse", "--git-dir"], cwd=path)
    return code == 0


def collect_staged(path: Path, all_files: bool = False) -> list[str]:
    """
    Archivos que van al próximo commit — solo `--cached`.
    A diferencia de pre-push-guard NO incluye working tree ni untracked:
    esos no están en el commit que se está gestando.
    """
    if all_files:
        code, out = run(["git", "ls-files"], cwd=path)
        return [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    code, out = run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=path,
    )
    if code != 0:
        return []
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return sorted(f for f in files if (path / f).exists())


def partition(files: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"yaml": [], "md": [], "py": []}
    for f in files:
        low = f.lower()
        if low.endswith((".yml", ".yaml")):
            buckets["yaml"].append(f)
        elif low.endswith(".md"):
            buckets["md"].append(f)
        elif low.endswith(".py"):
            buckets["py"].append(f)
    return buckets


def step_yaml(yaml_files: list[str], cwd: Path) -> StepResult:
    res = StepResult(name="yaml-control", files=yaml_files)
    if not yaml_files:
        res.skipped = True
        res.skip_reason = "sin archivos YAML staged"
        return res
    if not YAML_CONTROL.is_file():
        res.skipped = True
        res.skip_reason = f"yaml-control no instalado ({YAML_CONTROL})"
        return res
    t0 = time.time()
    code, out = run([sys.executable, str(YAML_CONTROL)], cwd=cwd)
    res.duration_s = time.time() - t0
    res.ok = code == 0
    res.output = out
    return res


def step_python(py_files: list[str], cwd: Path) -> StepResult:
    """Modo --parity-only: comprueba que el gate de lint declarado exista de
    verdad (config, CI y hook local). No invoca ruff, para no pasar de 2 s."""
    res = StepResult(name="python-lint-guard --parity-only", files=py_files)
    if not py_files:
        res.skipped = True
        res.skip_reason = "sin archivos Python staged"
        return res
    if not PY_LINT_GUARD.is_file():
        res.skipped = True
        res.skip_reason = f"python-lint-guard no instalado ({PY_LINT_GUARD})"
        return res
    t0 = time.time()
    code, out = run([sys.executable, str(PY_LINT_GUARD), "--parity-only"], cwd=cwd)
    res.duration_s = time.time() - t0
    res.ok = code == 0
    res.output = out
    return res


def step_md(md_files: list[str], cwd: Path) -> StepResult:
    res = StepResult(name="md-lint-fix --dry-run", files=md_files)
    if not md_files:
        res.skipped = True
        res.skip_reason = "sin archivos Markdown staged"
        return res
    if not MD_LINT_FIX.is_file():
        res.skipped = True
        res.skip_reason = f"md-lint-fix no instalado ({MD_LINT_FIX})"
        return res
    t0 = time.time()
    code, out = run([sys.executable, str(MD_LINT_FIX), "--dry-run"], cwd=cwd)
    res.duration_s = time.time() - t0
    res.ok = code == 0
    res.output = out
    return res


def render_header(cwd: Path, staged_files: list[str]) -> str:
    preview = ", ".join(staged_files[:6]) + ("…" if len(staged_files) > 6 else "")
    return (
        f"pre-commit-guard — repo: {cwd}\n"
        f"  staged: {len(staged_files)} archivo(s){' (' + preview + ')' if staged_files else ''}\n"
    )


def render_step(idx: int, total: int, res: StepResult) -> str:
    out = [f"[{idx}/{total}] {res.name} · {len(res.files)} archivo(s)"]
    if res.skipped:
        out.append(f"  ⊘ saltado — {res.skip_reason}")
        return "\n".join(out)
    if res.ok:
        out.append(f"  ✓ OK ({res.duration_s:.1f}s)")
    else:
        out.append(f"  ✗ FALLÓ ({res.duration_s:.1f}s)")
        if res.output.strip():
            for line in res.output.strip().splitlines():
                out.append(f"    {line}")
    return "\n".join(out)


HOOK_TEMPLATE = """#!/usr/bin/env bash
# Installed by pre-commit-guard. Skip with: git commit --no-verify
exec "{python}" "{script}" "$@"
"""


def install_hook(cwd: Path) -> int:
    if not is_git_repo(cwd):
        sys.stderr.write("ERROR: no es un repo git.\n")
        return 2
    code, gitdir = run(["git", "rev-parse", "--git-dir"], cwd=cwd)
    if code != 0:
        return 2
    hooks_dir = (cwd / gitdir.strip() / "hooks")
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "pre-commit"
    if target.exists():
        backup = target.with_suffix(".pre-commit.bak")
        if not backup.exists():
            shutil.copy2(target, backup)
            print(f"  Hook previo respaldado en {backup.name}")
    target.write_text(
        HOOK_TEMPLATE.format(
            python=sys.executable.replace("\\", "/"),
            script=str(Path(__file__).resolve()).replace("\\", "/"),
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(target, 0o755)
    except OSError:
        pass
    print(f"✓ Hook instalado en {target}")
    print("  Saltar con: git commit --no-verify")
    return 0


def uninstall_hook(cwd: Path) -> int:
    if not is_git_repo(cwd):
        sys.stderr.write("ERROR: no es un repo git.\n")
        return 2
    code, gitdir = run(["git", "rev-parse", "--git-dir"], cwd=cwd)
    if code != 0:
        return 2
    hooks_dir = cwd / gitdir.strip() / "hooks"
    target = hooks_dir / "pre-commit"
    backup = target.with_suffix(".pre-commit.bak")
    if backup.exists():
        shutil.move(str(backup), str(target))
        print(f"✓ Hook restaurado desde {backup.name}")
    elif target.exists():
        target.unlink()
        print(f"✓ Hook eliminado: {target}")
    else:
        print("  No había hook instalado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pre-commit-guard",
        description="Validación pre-commit del toolkit (yaml-control + md-lint-fix + python-lint-guard sobre staged).",
    )
    parser.add_argument("--all", action="store_true", help="Valida todos los archivos rastreados, no solo staged.")
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    parser.add_argument("--install-hook", action="store_true", help="Instala como git pre-commit hook (opt-in).")
    parser.add_argument("--uninstall-hook", action="store_true", help="Desinstala el hook.")
    args = parser.parse_args(argv)

    cwd = Path.cwd()

    if args.install_hook:
        return install_hook(cwd)
    if args.uninstall_hook:
        return uninstall_hook(cwd)

    if not is_git_repo(cwd):
        sys.stderr.write("ERROR: no es un repo git.\n")
        return 2

    staged = collect_staged(cwd, all_files=args.all)
    buckets = partition(staged)

    steps: list[StepResult] = [
        step_yaml(buckets["yaml"], cwd),
        step_md(buckets["md"], cwd),
        step_python(buckets["py"], cwd),
    ]

    total = len(steps)
    failed = False
    if not args.json:
        print(render_header(cwd, staged))

    grand_t0 = time.time()
    for idx, res in enumerate(steps, start=1):
        if not args.json:
            print(render_step(idx, total, res))
        if not res.skipped and not res.ok:
            failed = True
            if not args.json:
                print(f"\n❌ Bloqueado en step [{idx}/{total}]. Arregla y vuelve a intentar (o `git commit --no-verify` en emergencia).")
            break

    grand_t = time.time() - grand_t0

    if args.json:
        payload = {
            "cwd": str(cwd),
            "staged_files": staged,
            "steps": [
                {
                    "name": s.name, "files": s.files, "skipped": s.skipped,
                    "skip_reason": s.skip_reason, "ok": s.ok,
                    "duration_s": round(s.duration_s, 3), "output": s.output,
                }
                for s in steps
            ],
            "ok": not failed,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif not failed:
        print(f"\n✅ Todo verde. OK para `git commit` ({grand_t:.1f}s total).")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
