#!/usr/bin/env python3
"""
python-deps-pinning — mide qué parte del árbol de dependencias Python de un
repo es REALMENTE auditable, y por qué el resto no lo es.

Un scanner de vulnerabilidades solo puede pronunciarse sobre una dependencia
si sabe qué versión exacta está instalada. `requests` a secas, o
`requests>=2.0`, no resuelven a una versión: quedan fuera del scan. El
problema es que la mayoría de reportes no lo dicen — presentan "0
vulnerabilidades" sobre una superficie que nunca miraron.

Este skill calcula la cobertura real y nombra las dependencias invisibles.
Es el complemento natural de `security-audit`, que declara esa limitación
pero no la cuantifica por fichero.

Uso:
    python python_deps_pinning.py                  # reporte
    python python_deps_pinning.py --strict         # exit 1 si hay deps invisibles
    python python_deps_pinning.py --threshold 90   # exit 1 si cobertura < 90%
    python python_deps_pinning.py --json

Trabaja sobre Path.cwd(). Solo stdlib.
"""
from __future__ import annotations

import argparse
import json
import re
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

_VENDOR = {
    "node_modules", "target", "dist", "build", "site-packages",
    "__pycache__", "vendor_py", ".venv", "venv",
}

# Lockfiles por gestor. Si existe uno, las versiones exactas viven ahí aunque
# el manifest declare rangos — la superficie sí es auditable.
LOCKFILES = {
    "requirements.lock": "pip-tools",
    "requirements.txt.lock": "pip-tools",
    "poetry.lock": "poetry",
    "uv.lock": "uv",
    "Pipfile.lock": "pipenv",
    "pdm.lock": "pdm",
}

# Estados posibles de una dependencia declarada.
EXACT = "exact"        # ==1.2.3 · resoluble → auditable
LOCKED = "locked"      # rango, pero hay lockfile que lo fija → auditable
RANGE = "range"        # >=, ~=, ^, < · NO resoluble sin lockfile
BARE = "bare"          # sin especificador · NO resoluble
DIRECT = "direct"      # URL / VCS / editable · fuera de todo índice

AUDITABLE = {EXACT, LOCKED}


@dataclass
class Dep:
    name: str
    raw: str
    state: str
    source: str

    def as_dict(self) -> dict:
        return {"name": self.name, "raw": self.raw, "state": self.state, "source": self.source}


@dataclass
class Report:
    root: Path
    deps: list[Dep] = field(default_factory=list)
    lockfiles: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.deps)

    @property
    def auditable(self) -> int:
        return sum(1 for d in self.deps if d.state in AUDITABLE)

    @property
    def coverage(self) -> float:
        return 100.0 if self.total == 0 else round(100.0 * self.auditable / self.total, 1)

    @property
    def invisible(self) -> list[Dep]:
        return [d for d in self.deps if d.state not in AUDITABLE]


def _skip(p: Path, root: Path) -> bool:
    try:
        parts = p.relative_to(root).parts[:-1]
    except ValueError:
        return True
    return any(part in _VENDOR or (part.startswith(".") and part != ".") for part in parts)


def rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ------------------------------------------------------------------ parsing

_REQ_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"\s*(?P<extras>\[[^\]]*\])?"
    r"\s*(?P<spec>.*)$"
)


def classify_spec(spec: str, has_lock: bool) -> str:
    spec = spec.strip()
    # Quitar marcadores de entorno y comentarios: no afectan a la resolución.
    spec = spec.split(";")[0].split("#")[0].strip()
    if not spec:
        return LOCKED if has_lock else BARE
    if "==" in spec and "!=" not in spec.replace("!=", ""):
        # `==1.2.3` resuelve; `==1.2.*` no fija una versión concreta.
        return EXACT if not re.search(r"==\s*[^,\s]*\*", spec) else (LOCKED if has_lock else RANGE)
    return LOCKED if has_lock else RANGE


def parse_requirements(path: Path, root: Path, has_lock: bool) -> list[Dep]:
    out: list[Dep] = []
    src = rel(root, path)
    for line in _read(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            # -r otro.txt, -c constraints.txt, -e ./pkg, --index-url …
            if line.startswith(("-e", "--editable")):
                out.append(Dep(name=line, raw=line, state=DIRECT, source=src))
            continue
        if re.match(r"^[a-z+]+://", line) or line.startswith("git+"):
            out.append(Dep(name=line[:60], raw=line, state=DIRECT, source=src))
            continue
        m = _REQ_LINE.match(line)
        if not m:
            continue
        name = m.group("name")
        spec = m.group("spec") or ""
        if "@" in spec:  # PEP 508 direct reference: pkg @ https://…
            out.append(Dep(name=name, raw=line, state=DIRECT, source=src))
            continue
        out.append(Dep(name=name, raw=line, state=classify_spec(spec, has_lock), source=src))
    return out


def parse_pyproject(path: Path, root: Path, has_lock: bool) -> list[Dep]:
    out: list[Dep] = []
    src = rel(root, path)
    text = _read(path)
    data: dict = {}
    if tomllib:
        try:
            data = tomllib.loads(text)
        except Exception:
            data = {}

    def add_pep621(items) -> None:
        for item in items or []:
            if not isinstance(item, str):
                continue
            m = _REQ_LINE.match(item)
            if not m:
                continue
            spec = m.group("spec") or ""
            state = DIRECT if "@" in spec else classify_spec(spec, has_lock)
            out.append(Dep(name=m.group("name"), raw=item, state=state, source=src))

    project = data.get("project") or {}
    add_pep621(project.get("dependencies"))
    for group in (project.get("optional-dependencies") or {}).values():
        add_pep621(group)
    for group in (data.get("dependency-groups") or {}).values():
        add_pep621(group)

    # Poetry usa tablas, no strings PEP 508.
    poetry = ((data.get("tool") or {}).get("poetry") or {})
    for section in ("dependencies", "dev-dependencies"):
        for name, spec in (poetry.get(section) or {}).items():
            if name.lower() == "python":
                continue
            raw = f"{name} = {spec!r}"
            if isinstance(spec, dict):
                state = DIRECT if ("git" in spec or "url" in spec or "path" in spec) else (
                    LOCKED if has_lock else RANGE
                )
            elif isinstance(spec, str):
                state = EXACT if re.fullmatch(r"\d[\w.\-+]*", spec.strip()) else (
                    LOCKED if has_lock else RANGE
                )
            else:
                state = LOCKED if has_lock else RANGE
            out.append(Dep(name=name, raw=raw, state=state, source=src))

    if not data and text:
        # tomllib ausente o TOML inválido: al menos avisamos de que hay manifest.
        out.append(Dep(name="(pyproject no parseable)", raw="", state=BARE, source=src))
    return out


def scan(root: Path) -> Report:
    rep = Report(root=root)

    for name, manager in LOCKFILES.items():
        for hit in root.rglob(name):
            if not _skip(hit, root):
                rep.lockfiles[rel(root, hit)] = manager

    # Un lockfile en la raíz cubre el manifest de la raíz. Ser conservador:
    # solo se considera cubierto si el lockfile vive en el mismo directorio.
    lock_dirs = {str(Path(k).parent) for k in rep.lockfiles}

    for req in sorted(root.rglob("requirements*.txt")):
        if _skip(req, root):
            continue
        has_lock = str(Path(rel(root, req)).parent) in lock_dirs
        rep.sources.append(rel(root, req))
        rep.deps.extend(parse_requirements(req, root, has_lock))

    for pp in sorted(root.rglob("pyproject.toml")):
        if _skip(pp, root):
            continue
        has_lock = str(Path(rel(root, pp)).parent) in lock_dirs
        rep.sources.append(rel(root, pp))
        rep.deps.extend(parse_pyproject(pp, root, has_lock))

    if not rep.sources:
        rep.notes.append("No se encontró ningún manifest Python (requirements*.txt / pyproject.toml).")
    if not rep.lockfiles and rep.deps:
        rep.notes.append(
            "No hay lockfile. Sin él, cualquier rango de versión es irreproducible: "
            "dos instalaciones del mismo commit pueden traer versiones distintas."
        )
    return rep


# ------------------------------------------------------------------- salida

RECIPE = {
    "pip-tools": "pip-compile requirements.in -o requirements.txt --generate-hashes",
    "uv": "uv pip compile requirements.in -o requirements.txt",
    "poetry": "poetry lock",
    "pdm": "pdm lock",
    "pipenv": "pipenv lock",
}


def render(rep: Report) -> str:
    lines = [
        f"python-deps-pinning — repo: {rep.root}",
        "",
        f"Manifests analizados: {len(rep.sources)}",
    ]
    for s in rep.sources:
        lines.append(f"  · {s}")
    if rep.lockfiles:
        lines.append("")
        lines.append("Lockfiles encontrados:")
        for path, manager in sorted(rep.lockfiles.items()):
            lines.append(f"  · {path}  ({manager})")
    lines.append("")

    lines.append("COBERTURA REAL DEL SCAN DE VULNERABILIDADES")
    lines.append("  " + "-" * 58)
    lines.append(f"  dependencias declaradas   : {rep.total}")
    lines.append(f"  resolubles a versión exacta: {rep.auditable}")
    lines.append(f"  invisibles para el scanner : {len(rep.invisible)}")
    lines.append(f"  cobertura                  : {rep.coverage}%")
    lines.append("")

    if rep.invisible:
        by_source: dict[str, list[Dep]] = {}
        for d in rep.invisible:
            by_source.setdefault(d.source, []).append(d)
        lines.append("FUERA DEL SCAN — un CVE en estas dependencias no se detectaría")
        for source, deps in sorted(by_source.items()):
            lines.append(f"  {source}  ({len(deps)})")
            for d in deps[:12]:
                reason = {
                    RANGE: "rango sin lockfile",
                    BARE: "sin especificador de versión",
                    DIRECT: "referencia directa (URL/VCS/editable)",
                }.get(d.state, d.state)
                lines.append(f"    · {d.name:<28} {reason}")
            if len(deps) > 12:
                lines.append(f"    … y {len(deps) - 12} más")
        lines.append("")

    for note in rep.notes:
        lines.append(f"⚠ {note}")
    if rep.notes:
        lines.append("")

    if rep.invisible:
        lines.append("CÓMO CERRARLO")
        managers = set(rep.lockfiles.values()) or {"pip-tools", "uv"}
        for manager in sorted(managers):
            lines.append(f"  {manager:<10} → {RECIPE.get(manager, '(sin receta)')}")
        lines.append("")
        lines.append(
            "  Después vuelve a correr `security-audit`: la cobertura del reporte\n"
            "  subirá, y las dependencias que hoy no se miran pasarán a auditarse."
        )
    else:
        lines.append("✅ Toda dependencia declarada resuelve a una versión concreta.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python-deps-pinning",
        description="Mide qué parte de las dependencias Python es realmente auditable.",
    )
    ap.add_argument("--strict", action="store_true", help="Exit 1 si hay alguna dependencia invisible.")
    ap.add_argument("--threshold", type=float, default=None, metavar="PCT",
                    help="Exit 1 si la cobertura queda por debajo de este porcentaje.")
    ap.add_argument("--json", action="store_true", help="Salida JSON.")
    args = ap.parse_args(argv)

    rep = scan(Path.cwd())

    if args.json:
        print(json.dumps({
            "root": str(rep.root),
            "sources": rep.sources,
            "lockfiles": rep.lockfiles,
            "total": rep.total,
            "auditable": rep.auditable,
            "coverage": rep.coverage,
            "invisible": [d.as_dict() for d in rep.invisible],
            "notes": rep.notes,
        }, indent=2, ensure_ascii=False))
    else:
        print(render(rep))

    if args.threshold is not None and rep.coverage < args.threshold:
        return 1
    if args.strict and rep.invisible:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
