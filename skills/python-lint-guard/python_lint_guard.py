#!/usr/bin/env python3
"""
python-lint-guard — el gate de Python que falta antes de commit/push.

No es un wrapper de ruff. Su aporte propio es la **paridad de toolchain**:
detecta qué linter/formateador DECLARA el repo (pyproject, ruff.toml,
setup.cfg, .flake8, tox.ini, .pre-commit-config.yaml) y lo compara con lo que
el CI REALMENTE ejecuta (.github/workflows). Esa deriva es la causa raíz de la
mayoría de los commits "fix(lint): ..." que solo existen para apagar un CI en
rojo: el repo declara ruff pero el CI corre black, o hay linter declarado y
ningún gate en CI, o conviven dos formateadores que se pisan.

Sobre eso, si `ruff` está disponible, añade el análisis de violaciones y
separa lo MECÁNICO (auto-corregible sin criterio) de lo que exige JUICIO
humano — porque `--fix` a ciegas sobre F841 puede borrar la evidencia de un bug.

Uso:
    python python_lint_guard.py                 # diff vs git, reporte
    python python_lint_guard.py --all           # todos los .py rastreados
    python python_lint_guard.py --fix           # auto-fix solo del set mecánico
    python python_lint_guard.py --parity-only   # solo la capa de paridad
    python python_lint_guard.py --json          # salida JSON

Trabaja sobre Path.cwd(). Núcleo en stdlib; `ruff` es opt-in y degrada.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        pass

_VENDOR = {"node_modules", "target", "dist", "build", "site-packages", "__pycache__"}

# Herramientas que nos interesan, con el/los rol(es) que cumplen. Dos
# herramientas que comparten rol es un conflicto, no una redundancia.
#
# `ruff` cumple DOS roles a la vez, y por eso el rol tiene que ser un conjunto
# y no una etiqueta: `ruff` + `black` es el conflicto de formateadores más
# frecuente, y compararlos como cadenas ("linter+formatter" vs "formatter") lo
# dejaría pasar.
TOOL_ROLES = {
    "ruff": frozenset({"linter", "formatter"}),
    "black": frozenset({"formatter"}),
    "autopep8": frozenset({"formatter"}),
    "yapf": frozenset({"formatter"}),
    "flake8": frozenset({"linter"}),
    "pylint": frozenset({"linter"}),
    "isort": frozenset({"import-sorter"}),
    "mypy": frozenset({"type-checker"}),
}

# Etiqueta legible para la tabla del reporte.
TOOL_ROLE = {
    tool: "+".join(sorted(roles)) for tool, roles in TOOL_ROLES.items()
}

# Reglas ruff que se pueden corregir automáticamente sin perder información.
MECHANICAL = {
    "I001",   # bloque de imports sin ordenar
    "F401",   # import sin usar
    "UP006",  # typing.List -> list
    "UP035",  # import obsoleto de typing
    "W291",   # espacio final
    "W293",   # línea en blanco con espacios
    "W391",   # líneas en blanco al final del fichero
    "RUF100", # noqa innecesario
    "COM812", # coma final ausente
    "Q000",   # comillas inconsistentes
}

# Reglas que NO se auto-corrigen: borrar el síntoma puede borrar el bug.
JUDGMENT = {
    "F841": "variable asignada y nunca usada — puede ser un bug real, no basura",
    "E741": "nombre ambiguo (l, I, O) — renombrar es decisión de diseño",
    "E402": "import fuera del top — a veces es intencional (side-effects, sys.path)",
    "E501": "línea demasiado larga — la arregla el formateador, no el linter",
    "S110": "try-except-pass — silenciar excepciones puede ocultar fallos",
    "S112": "try-except-continue — idem",
    "C901": "complejidad excesiva — exige refactor, no un fix",
    "B008": "llamada en el default de un argumento — semántica, no estilo",
}


@dataclass
class Finding:
    level: str          # "error" | "warn" | "info"
    code: str
    message: str
    hint: str = ""

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message, "hint": self.hint}


@dataclass
class Report:
    root: Path
    files: list[str] = field(default_factory=list)
    declared: dict[str, str] = field(default_factory=dict)   # tool -> dónde se declara
    ci_tools: dict[str, str] = field(default_factory=dict)   # tool -> workflow que lo corre
    findings: list[Finding] = field(default_factory=list)
    violations: dict[str, int] = field(default_factory=dict)  # code -> nº ocurrencias
    ruff_available: bool = False
    hook_installed: bool = False
    fixed: int = 0

    @property
    def ok(self) -> bool:
        return not any(f.level == "error" for f in self.findings)


# --------------------------------------------------------------------------- git

def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (FileNotFoundError, OSError) as exc:
        return 127, str(exc)


def is_git_repo(root: Path) -> bool:
    return run(["git", "rev-parse", "--git-dir"], cwd=root)[0] == 0


def collect_python_files(root: Path, all_files: bool) -> list[str]:
    """Los .py en scope: por defecto el diff (working tree + untracked), o todos."""
    if not is_git_repo(root):
        return sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*.py")
            if not _skip(p, root)
        )

    if all_files:
        code, out = run(["git", "ls-files", "*.py"], cwd=root)
        names = out.splitlines() if code == 0 else []
    else:
        names = []
        for args in (
            ["git", "diff", "--name-only", "HEAD"],
            ["git", "diff", "--name-only", "--cached"],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ):
            code, out = run(args, cwd=root)
            if code == 0:
                names.extend(out.splitlines())

    seen: set[str] = set()
    for n in names:
        n = n.strip()
        if n.endswith(".py") and (root / n).is_file() and not _skip(root / n, root):
            seen.add(n.replace("\\", "/"))
    return sorted(seen)


def _skip(p: Path, root: Path) -> bool:
    try:
        parts = p.relative_to(root).parts[:-1]
    except ValueError:
        return True
    return any(part in _VENDOR or (part.startswith(".") and part != ".") for part in parts)


# ------------------------------------------------------------------- declaración

def detect_declared(root: Path) -> dict[str, str]:
    """Qué herramientas declara el repo, y en qué fichero."""
    found: dict[str, str] = {}

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = _read(pyproject)
        data = {}
        if tomllib:
            try:
                data = tomllib.loads(text)
            except Exception:
                data = {}
        tools = (data.get("tool") or {}) if isinstance(data, dict) else {}
        for name in TOOL_ROLE:
            if name in tools:
                found[name] = "pyproject.toml"
            elif not tools and re.search(rf"(?m)^\[tool\.{re.escape(name)}\b", text):
                # tomllib no disponible o TOML inválido: caemos a regex
                found[name] = "pyproject.toml"
        # dependencias declaradas (dev-deps, optional-deps) también cuentan
        for name in TOOL_ROLE:
            if name not in found and re.search(rf'["\']{re.escape(name)}\s*[><=~!]', text):
                found[name] = "pyproject.toml (dependencia)"

    for fname in ("ruff.toml", ".ruff.toml"):
        if (root / fname).is_file():
            found["ruff"] = fname

    for fname in ("setup.cfg", "tox.ini"):
        f = root / fname
        if f.is_file():
            text = _read(f)
            for name in ("flake8", "isort", "mypy", "pylint"):
                if re.search(rf"(?m)^\[{re.escape(name)}\]", text):
                    found.setdefault(name, fname)

    if (root / ".flake8").is_file():
        found.setdefault("flake8", ".flake8")

    precommit = root / ".pre-commit-config.yaml"
    if precommit.is_file():
        text = _read(precommit)
        for name in TOOL_ROLE:
            if re.search(rf"\b{re.escape(name)}\b", text):
                found.setdefault(name, ".pre-commit-config.yaml")

    return found


def detect_ci_tools(root: Path) -> dict[str, str]:
    """Qué herramientas ejecuta realmente el CI, y en qué workflow."""
    found: dict[str, str] = {}
    wfdir = root / ".github" / "workflows"
    if not wfdir.is_dir():
        return found
    for wf in sorted(list(wfdir.glob("*.yml")) + list(wfdir.glob("*.yaml"))):
        text = _read(wf)
        # Solo líneas de ejecución (run:, uses:) — evita falsos positivos por
        # comentarios o por el nombre del job.
        runnable = "\n".join(
            line for line in text.splitlines()
            if re.search(r"^\s*(-?\s*(run|uses)\s*:|\s+)", line)
        )
        for name in TOOL_ROLE:
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", runnable):
                found.setdefault(name, wf.name)
    return found


def detect_hook_installed(root: Path) -> bool:
    """True si el hook pre-commit está realmente instalado en .git/hooks."""
    code, gitdir = run(["git", "rev-parse", "--git-dir"], cwd=root)
    if code != 0:
        return False
    hook = (root / gitdir.strip() / "hooks" / "pre-commit")
    if not hook.is_file():
        return False
    # git deja un .sample por defecto; solo cuenta si referencia a pre-commit
    # o a un guard del toolkit.
    body = _read(hook)
    return bool(re.search(r"pre[-_]commit|guard", body, re.IGNORECASE))


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""


# ------------------------------------------------------------------------ paridad

def check_parity(rep: Report) -> None:
    """La capa que ningún linter cubre: el repo dice una cosa y el CI hace otra."""
    declared, ci = rep.declared, rep.ci_tools

    # 1. Declarado pero el CI no lo corre → el gate no existe donde importa.
    for tool, where in sorted(declared.items()):
        if tool not in ci:
            rep.findings.append(Finding(
                "error", "PARITY-NO-CI",
                f"'{tool}' está declarado en {where} pero ningún workflow lo ejecuta",
                f"añade un step que corra {tool} en .github/workflows/, o quita la "
                f"declaración si ya no se usa",
            ))

    # 2. El CI lo corre pero no está declarado → config implícita, no reproducible
    #    en local: el dev no puede correr lo mismo que el CI antes de pushear.
    for tool, where in sorted(ci.items()):
        if tool not in declared:
            rep.findings.append(Finding(
                "warn", "PARITY-NO-CONFIG",
                f"el workflow {where} ejecuta '{tool}' pero el repo no lo declara",
                f"declara {tool} en pyproject.toml para que local y CI usen la misma config",
            ))

    # 3. Dos herramientas que comparten rol → se pisan entre sí en cada commit.
    by_role: dict[str, list[str]] = {}
    for tool in set(declared) | set(ci):
        for role in TOOL_ROLES[tool]:
            by_role.setdefault(role, []).append(tool)
    for role, tools in sorted(by_role.items()):
        if role in ("formatter", "linter") and len(tools) > 1:
            rep.findings.append(Finding(
                "error", "PARITY-CONFLICT",
                f"conviven {len(tools)} herramientas con rol '{role}': {', '.join(sorted(tools))}",
                "elige una — dos formateadores reescriben el mismo fichero en cada "
                "pasada y generan commits de ida y vuelta",
            ))

    # 4. Hay Python pero ningún gate en ninguna parte.
    if rep.files and not declared and not ci:
        rep.findings.append(Finding(
            "warn", "PARITY-NO-GATE",
            f"{len(rep.files)} fichero(s) .py y ningún linter declarado ni en CI",
            "añade ruff: `[tool.ruff]` en pyproject.toml + un step en el workflow",
        ))

    # 5. El gate existe en el papel pero no en la máquina del dev.
    #    Este es el caso que más commits "fix(lint)" produce: el repo declara
    #    .pre-commit-config.yaml, el CI corre el linter, pero nadie instaló el
    #    hook — así que las violaciones se descubren en CI, no antes de pushear.
    if (rep.root / ".pre-commit-config.yaml").is_file() and not rep.hook_installed:
        rep.findings.append(Finding(
            "error", "PARITY-HOOK-ABSENT",
            ".pre-commit-config.yaml existe pero el hook local NO está instalado",
            "instálalo con `pre-commit install` — sin él el linter solo corre en "
            "CI y cada violación cuesta un commit extra de arreglo",
        ))


# --------------------------------------------------------------------------- ruff

def run_ruff(rep: Report, files: list[str], fix: bool) -> None:
    if shutil.which("ruff") is None:
        rep.findings.append(Finding(
            "info", "RUFF-ABSENT",
            "ruff no está instalado — capa de violaciones saltada",
            "pip install ruff (opcional: el análisis de paridad ya se ejecutó)",
        ))
        return
    rep.ruff_available = True
    if not files:
        return

    if fix:
        # Acotado al set mecánico: nunca --fix global.
        code, _ = run(
            ["ruff", "check", "--select", ",".join(sorted(MECHANICAL)), "--fix", "--quiet", *files],
            cwd=rep.root,
        )
        if code not in (0, 1):
            rep.findings.append(Finding("warn", "RUFF-FIX-FAIL", "`ruff check --fix` terminó con error"))

    code, out = run(["ruff", "check", "--output-format", "json", *files], cwd=rep.root)
    if code not in (0, 1):
        rep.findings.append(Finding("warn", "RUFF-FAIL", f"ruff no pudo analizar: {out.strip()[:200]}"))
        return
    try:
        items = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        rep.findings.append(Finding("warn", "RUFF-PARSE", "salida de ruff no parseable como JSON"))
        return

    for item in items:
        rule = item.get("code") or "?"
        rep.violations[rule] = rep.violations.get(rule, 0) + 1

    for rule, count in sorted(rep.violations.items(), key=lambda kv: -kv[1]):
        if rule in MECHANICAL:
            rep.findings.append(Finding(
                "error", rule, f"{count} ocurrencia(s) — mecánico",
                "se corrige con --fix, sin criterio humano",
            ))
        else:
            rep.findings.append(Finding(
                "error", rule,
                f"{count} ocurrencia(s) — requiere criterio",
                JUDGMENT.get(rule, "revisar manualmente: no está en el set auto-corregible"),
            ))


# -------------------------------------------------------------------------- salida

def render(rep: Report, parity_only: bool) -> str:
    tools = sorted(set(rep.declared) | set(rep.ci_tools))
    # Anchos dinámicos: ".pre-commit-config.yaml" no cabe en una columna fija.
    w_decl = max([len("declarado en")] + [len(rep.declared.get(t, "—")) for t in tools]) + 2

    lines = [
        f"python-lint-guard — repo: {rep.root}",
        f"  ficheros .py en scope: {len(rep.files)}",
        "",
        "Toolchain declarado vs. ejecutado en CI",
        "  " + "-" * (14 + 18 + w_decl + 12),
        f"  {'herramienta':<14}{'rol':<18}{'declarado en':<{w_decl}}{'CI'}",
    ]
    if not tools:
        lines.append("  (ninguna herramienta detectada)")
    for tool in tools:
        decl = rep.declared.get(tool, "—")
        ci = rep.ci_tools.get(tool, "—")
        lines.append(f"  {tool:<14}{TOOL_ROLE[tool]:<18}{decl:<{w_decl}}{ci}")
    lines.append("")

    errors = [f for f in rep.findings if f.level == "error"]
    warns = [f for f in rep.findings if f.level == "warn"]
    infos = [f for f in rep.findings if f.level == "info"]

    if not parity_only and rep.ruff_available:
        total = sum(rep.violations.values())
        mech = sum(c for r, c in rep.violations.items() if r in MECHANICAL)
        lines.append(f"Violaciones ruff: {total} ({mech} mecánicas, {total - mech} con criterio)")
        lines.append("")

    for label, group, mark in (("ERRORES", errors, "✗"), ("AVISOS", warns, "⚠"), ("INFO", infos, "ℹ")):
        if not group:
            continue
        lines.append(f"{label}")
        for f in group:
            lines.append(f"  {mark} [{f.code}] {f.message}")
            if f.hint:
                lines.append(f"      → {f.hint}")
        lines.append("")

    if rep.fixed:
        lines.append(f"Auto-corregidos: {rep.fixed} fichero(s) con el set mecánico.")
        lines.append("")

    lines.append("✅ Sin bloqueos." if rep.ok else "❌ Hay errores que bloquean commit/push.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python-lint-guard", description="Gate de lint Python con control de paridad local↔CI.")
    ap.add_argument("--all", action="store_true", help="Analiza todos los .py rastreados, no solo el diff.")
    ap.add_argument("--fix", action="store_true", help="Auto-corrige SOLO el set mecánico (nunca el que exige criterio).")
    ap.add_argument("--parity-only", action="store_true", help="Solo la capa de paridad toolchain; no invoca ruff.")
    ap.add_argument("--json", action="store_true", help="Salida JSON.")
    args = ap.parse_args(argv)

    root = Path.cwd()
    rep = Report(root=root)
    rep.files = collect_python_files(root, all_files=args.all)
    rep.declared = detect_declared(root)
    rep.ci_tools = detect_ci_tools(root)
    rep.hook_installed = detect_hook_installed(root)

    check_parity(rep)
    if not args.parity_only:
        before = len(rep.files)
        run_ruff(rep, rep.files, fix=args.fix)
        if args.fix:
            rep.fixed = before

    if args.json:
        print(json.dumps({
            "root": str(rep.root),
            "files": rep.files,
            "declared": rep.declared,
            "ci_tools": rep.ci_tools,
            "violations": rep.violations,
            "ruff_available": rep.ruff_available,
            "findings": [f.as_dict() for f in rep.findings],
            "ok": rep.ok,
        }, indent=2, ensure_ascii=False))
    else:
        print(render(rep, parity_only=args.parity_only))

    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
