"""Scan a repository for Python version declarations and report drift.

Usage:
    python scan.py                  # scan cwd, report drift
    python scan.py --json           # JSON output (for integrations)
    python scan.py --fix X.Y        # propose diff to align everything to X.Y
                                    # (does NOT write — caller must confirm)
    python scan.py --root <path>    # scan a different repo
    python scan.py --apply X.Y      # actually write the changes (CALLER MUST CONFIRM)

Exits 0 if no drift, 1 if drift detected, 2 on internal error.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys

# Force UTF-8 stdout/stderr on Windows so box-drawing chars don't break.
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


# ──────────────────────────────────────────────────────────────────────────────
# Findings
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    source: str         # human-readable label
    file: str           # relative path
    field: str          # which field/key
    value: str          # what we found
    versions: list[str] = field(default_factory=list)  # parsed versions if any
    note: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    has_drift: bool = False
    canonical_suggestion: str | None = None
    diagnostics: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────────────────────────────────────────

PY_VER_RE = re.compile(r"\b3\.\d{1,2}(?:\.\d+)?\b")
PY_TAG_RE = re.compile(r"\bpy3(\d{1,2})\b")


def parse_pyproject(root: Path) -> list[Finding]:
    p = root / "pyproject.toml"
    if not p.exists():
        return []
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    out: list[Finding] = []
    rel = p.relative_to(root).as_posix()

    project = data.get("project", {})
    if "requires-python" in project:
        v = project["requires-python"]
        out.append(Finding("pyproject requires-python", rel, "project.requires-python", v, PY_VER_RE.findall(v)))
    cls = project.get("classifiers", []) or []
    versions = sorted({m.group(0) for c in cls for m in PY_VER_RE.finditer(c)})
    if versions:
        out.append(Finding("pyproject classifiers", rel, "project.classifiers", ", ".join(versions), versions))

    tool = data.get("tool", {})
    ruff = tool.get("ruff", {})
    tv = ruff.get("target-version")
    if tv:
        out.append(Finding("ruff target-version", rel, "tool.ruff.target-version", tv, [_tag_to_dotted(tv)]))
    ruff_format = ruff.get("format", {})
    if ruff_format.get("target-version"):
        v = ruff_format["target-version"]
        out.append(Finding("ruff.format target-version", rel, "tool.ruff.format.target-version", v, [_tag_to_dotted(v)]))

    mypy = tool.get("mypy", {})
    if "python_version" in mypy:
        v = str(mypy["python_version"])
        out.append(Finding("mypy python_version", rel, "tool.mypy.python_version", v, PY_VER_RE.findall(v) or [v]))

    black = tool.get("black", {})
    if "target-version" in black:
        v = black["target-version"]
        if isinstance(v, list):
            vs = [_tag_to_dotted(x) for x in v]
            out.append(Finding("black target-version", rel, "tool.black.target-version", ",".join(v), vs))

    return out


def _tag_to_dotted(tag: str) -> str:
    """py310 → 3.10."""
    m = PY_TAG_RE.match(tag)
    if m:
        n = m.group(1)
        return f"3.{n}" if len(n) <= 2 else f"3.{n[:-1]}.{n[-1]}"
    return tag


def parse_dockerfiles(root: Path) -> list[Finding]:
    out: list[Finding] = []
    skip_dirs = {".venv", "venv", "node_modules", ".git", "build", "dist", "site-packages",
                 ".claude", ".claire", ".tox", ".nox", "__pycache__", "dist_installer", "adicional"}
    for p in list(root.glob("Dockerfile*")) + list(root.glob("**/Dockerfile*")):
        if any(part in skip_dirs for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r"^FROM\s+python:([^\s\n]+)", text, flags=re.MULTILINE):
            full = m.group(1)
            vers = PY_VER_RE.findall(full) or [full]
            out.append(Finding("Dockerfile FROM", rel, "FROM python:...", full, vers))
        for m in re.finditer(r"^ARG\s+PYTHON_VERSION\s*=\s*([^\s\n]+)", text, flags=re.MULTILINE):
            v = m.group(1).strip("\"'")
            out.append(Finding("Dockerfile ARG PYTHON_VERSION", rel, "ARG PYTHON_VERSION", v, PY_VER_RE.findall(v) or [v]))
    return out


def parse_workflows(root: Path) -> list[Finding]:
    out: list[Finding] = []
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.exists() or yaml is None:
        return out
    for p in wf_dir.glob("*.y*ml"):
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except Exception as e:
            out.append(Finding(f"workflow parse error", rel, "(yaml)", str(e), [], note="could not parse"))
            continue
        if not isinstance(data, dict):
            continue
        jobs = data.get("jobs", {}) or {}
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            # Matrix python-version
            strategy = (job.get("strategy") or {}).get("matrix") or {}
            mv = strategy.get("python-version")
            if mv:
                if isinstance(mv, list):
                    vs = [str(x) for x in mv]
                    out.append(Finding(f"workflow matrix [{job_name}]", rel, "strategy.matrix.python-version", ", ".join(vs), vs))
                else:
                    out.append(Finding(f"workflow matrix [{job_name}]", rel, "strategy.matrix.python-version", str(mv), PY_VER_RE.findall(str(mv)) or [str(mv)]))
            # Steps using setup-python
            for step in job.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses", "")
                if "setup-python" in uses:
                    pv = (step.get("with") or {}).get("python-version")
                    if pv is not None:
                        if isinstance(pv, list):
                            vs = [str(x) for x in pv]
                            label = "step setup-python (list)"
                        else:
                            vs = PY_VER_RE.findall(str(pv)) or [str(pv)]
                            label = "step setup-python"
                        # ignore matrix placeholders
                        if "${{" in str(pv):
                            continue
                        out.append(Finding(f"workflow [{job_name}]", rel, label, str(pv), vs))
    return out


def parse_python_version(root: Path) -> list[Finding]:
    p = root / ".python-version"
    if not p.exists():
        return []
    v = p.read_text(encoding="utf-8").strip()
    return [Finding(".python-version (pyenv)", p.name, "(file content)", v, PY_VER_RE.findall(v) or [v])]


def parse_runtime_txt(root: Path) -> list[Finding]:
    p = root / "runtime.txt"
    if not p.exists():
        return []
    v = p.read_text(encoding="utf-8").strip()
    return [Finding("runtime.txt (Heroku)", p.name, "(file content)", v, PY_VER_RE.findall(v) or [v])]


def parse_tox(root: Path) -> list[Finding]:
    p = root / "tox.ini"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    envs = set(PY_TAG_RE.findall(text))
    if envs:
        vs = sorted({_tag_to_dotted(f"py{e}") for e in envs})
        return [Finding("tox.ini envlist", "tox.ini", "[tox]envlist", ",".join(vs), vs)]
    return []


def parse_noxfile(root: Path) -> list[Finding]:
    p = root / "noxfile.py"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    vs = sorted(set(PY_VER_RE.findall(text)))
    if vs:
        return [Finding("noxfile.py", "noxfile.py", "@nox.session(python=...)", ",".join(vs), vs)]
    return []


def parse_precommit(root: Path) -> list[Finding]:
    p = root / ".pre-commit-config.yaml"
    if not p.exists() or yaml is None:
        return []
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[Finding] = []
    default = (data or {}).get("default_language_version", {}) or {}
    py = default.get("python")
    if py:
        out.append(Finding("pre-commit default_language_version", ".pre-commit-config.yaml", "default_language_version.python", str(py), PY_VER_RE.findall(str(py)) or [str(py)]))
    return out


def parse_readme(root: Path) -> list[Finding]:
    p = root / "README.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    # Match "Python 3.X" or "Python 3.X+" mentions in first 200 lines
    head = "\n".join(text.splitlines()[:200])
    vs = sorted({m.group(0) for m in re.finditer(r"Python\s+(3\.\d{1,2})\+?", head, flags=re.IGNORECASE)})
    if vs:
        return [Finding("README.md menciones (informativo)", "README.md", "(texto)", "; ".join(vs), [PY_VER_RE.search(v).group(0) for v in vs if PY_VER_RE.search(v)], note="informativo, no bloqueante")]
    return []


PARSERS = [
    parse_pyproject,
    parse_dockerfiles,
    parse_workflows,
    parse_python_version,
    parse_runtime_txt,
    parse_tox,
    parse_noxfile,
    parse_precommit,
    parse_readme,
]


# ──────────────────────────────────────────────────────────────────────────────
# Analysis
# ──────────────────────────────────────────────────────────────────────────────

def _versions_of(f: Finding) -> set[tuple[int, int]]:
    out = set()
    for v in f.versions:
        m = re.match(r"(\d+)\.(\d+)", str(v))
        if m:
            out.add((int(m.group(1)), int(m.group(2))))
    return out


def analyze(findings: list[Finding]) -> Report:
    rep = Report(findings=findings)
    # Collect non-informational findings
    actionable = [f for f in findings if "informativo" not in f.note]
    if not actionable:
        rep.diagnostics.append("No Python version declarations found in this repo.")
        return rep

    # Collect set of major.minor across actionable findings
    seen: dict[tuple[int, int], list[str]] = {}
    for f in actionable:
        for vt in _versions_of(f):
            seen.setdefault(vt, []).append(f.source)

    versions_sorted = sorted(seen)
    if len(versions_sorted) == 0:
        rep.diagnostics.append("Could not parse any major.minor version.")
        return rep

    # Heuristic: drift if MAX-MIN > 0 across single-value sources (matrices are OK by design)
    single_value_findings = [f for f in actionable if len(_versions_of(f)) == 1]
    distinct_single = sorted({list(_versions_of(f))[0] for f in single_value_findings if _versions_of(f)})
    if len(distinct_single) > 1:
        rep.has_drift = True
        # Canonical suggestion: median of single-value declarations
        mid = distinct_single[len(distinct_single) // 2]
        rep.canonical_suggestion = f"{mid[0]}.{mid[1]}"
        rep.diagnostics.append(
            f"Drift detectado entre fuentes single-value: {sorted({f'{v[0]}.{v[1]}' for v in distinct_single})}. "
            f"Sugerencia: alinear a {rep.canonical_suggestion}."
        )
    else:
        rep.diagnostics.append("Sin drift: todas las fuentes single-value coinciden.")
    return rep


# ──────────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────────

def render_table(rep: Report) -> str:
    if not rep.findings:
        return "No Python version declarations found.\n"
    rows = []
    for f in rep.findings:
        rows.append((f.source, f.file, f.value[:40]))
    w0 = max(len(r[0]) for r in rows) + 2
    w1 = max(len(r[1]) for r in rows) + 2
    lines = [f"{'Source':<{w0}}{'File':<{w1}}Value"]
    lines.append("─" * (w0 + w1 + 30))
    for r in rows:
        lines.append(f"{r[0]:<{w0}}{r[1]:<{w1}}{r[2]}")
    lines.append("")
    for d in rep.diagnostics:
        lines.append(d)
    if rep.canonical_suggestion:
        lines.append(f"\nSugerencia canónica: Python {rep.canonical_suggestion}")
    return "\n".join(lines) + "\n"


def render_json(rep: Report) -> str:
    return json.dumps({
        "has_drift": rep.has_drift,
        "canonical_suggestion": rep.canonical_suggestion,
        "diagnostics": rep.diagnostics,
        "findings": [
            {"source": f.source, "file": f.file, "field": f.field, "value": f.value, "versions": f.versions, "note": f.note}
            for f in rep.findings
        ],
    }, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Fix proposal (no writes by default)
# ──────────────────────────────────────────────────────────────────────────────

def propose_fixes(rep: Report, target: str) -> list[str]:
    """Return human-readable list of proposed changes for target version X.Y."""
    m = re.match(r"3\.(\d{1,2})", target)
    if not m:
        return [f"ERROR: target inválido '{target}', usa formato '3.X'."]
    minor = int(m.group(1))
    proposals: list[str] = []
    for f in rep.findings:
        if "informativo" in f.note:
            continue
        current_vers = _versions_of(f)
        if not current_vers or (minor,) in {(v[1],) for v in current_vers}:
            continue
        # Multi-value sources (matrices) skip unless target falls outside range
        if len(current_vers) > 1:
            mins = min(v[1] for v in current_vers)
            maxs = max(v[1] for v in current_vers)
            if mins <= minor <= maxs:
                continue
            proposals.append(f"~ {f.file} :: {f.field} → ampliar/desplazar rango para incluir 3.{minor} (actual: {f.value})")
            continue
        # Single-value
        if f.field == "project.requires-python":
            proposals.append(f"~ {f.file} :: requires-python → '>=3.{minor}'")
        elif f.field.startswith("tool.ruff") or f.field.startswith("tool.black"):
            proposals.append(f"~ {f.file} :: {f.field} → 'py3{minor}'")
        elif f.field == "tool.mypy.python_version":
            proposals.append(f"~ {f.file} :: {f.field} → '3.{minor}'")
        elif "FROM python:" in f.field:
            proposals.append(f"~ {f.file} :: FROM python:3.{minor}-slim (o version major.minor preferida)")
        elif "setup-python" in f.field or "matrix.python-version" in f.field:
            proposals.append(f"~ {f.file} :: {f.field} → '3.{minor}'")
        elif f.source.startswith("pre-commit"):
            proposals.append(f"~ {f.file} :: default_language_version.python → 'python3.{minor}'")
        elif f.source.startswith(".python-version"):
            proposals.append(f"~ {f.file} (content) → '3.{minor}'")
        elif f.source.startswith("runtime.txt"):
            proposals.append(f"~ {f.file} (content) → 'python-3.{minor}'")
        else:
            proposals.append(f"~ {f.file} :: {f.source} → revisar manualmente (actual: {f.value})")
    if not proposals:
        proposals.append(f"Nada que cambiar — todo ya coherente con Python 3.{minor}.")
    return proposals


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Audit Python version coherence across a repo.")
    ap.add_argument("--root", default=".", help="Repo root (default: cwd)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--fix", metavar="X.Y", help="Propose diff to align to version X.Y (does NOT write)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: {root} no es directorio", file=sys.stderr)
        return 2

    all_findings: list[Finding] = []
    for parser in PARSERS:
        try:
            all_findings.extend(parser(root))
        except Exception as e:
            print(f"WARN: {parser.__name__} fallo: {e}", file=sys.stderr)

    rep = analyze(all_findings)

    if args.json:
        print(render_json(rep))
    else:
        print(render_table(rep))

    if args.fix:
        print("\nPropuesta de alineación (NO aplicada — requiere confirmación):")
        for line in propose_fixes(rep, args.fix):
            print(f"  {line}")

    return 1 if rep.has_drift else 0


if __name__ == "__main__":
    sys.exit(main())
