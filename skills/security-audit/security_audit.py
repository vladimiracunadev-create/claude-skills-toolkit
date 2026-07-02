#!/usr/bin/env python3
"""
security-audit — Audita un repositorio contra OSV.dev + CISA KEV + GHSA y
genera un informe Markdown reproducible. Opcionalmente aplica bumps.

Trabaja siempre desde Path.cwd(). Soporta PyPI, npm, Go, crates.io, RubyGems,
Maven, NuGet (via OSV.dev ecosystems).

Uso:
  python security_audit.py                       # sólo reporte
  python security_audit.py --apply               # + bump versiones
  python security_audit.py --apply --git         # + rama + commit
  python security_audit.py --apply --git --pr    # + PR auto-merge

Exit codes:
  0 = sin hallazgos
  1 = hallazgos reportados (no error de ejecución)
  2 = error de ejecución (red, archivo, etc.)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# UTF-8 stdout en Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


REPO = Path.cwd()
EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", ".pytest-tmp",
                "__pycache__", "dist", "build", ".claude", "vendor"}

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_QUERY_URL = "https://api.osv.dev/v1/query"
CISA_KEV_URL = ("https://www.cisa.gov/sites/default/files/feeds/"
                "known_exploited_vulnerabilities.json")
CACHE_DIR = Path.home() / ".cache" / "security-audit"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
KEV_CACHE = CACHE_DIR / "cisa_kev.json"
KEV_TTL_SECONDS = 86400  # 24h

PIN_PEP440 = re.compile(r"^([A-Za-z0-9._\-]+)==([A-Za-z0-9._\-+]+)\s*$")
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "moderate": 2, "low": 1, "unknown": 0}


# -------------------------------------------------------------------------
# Discovery — manifests
# -------------------------------------------------------------------------

def walk_repo(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            yield Path(root) / f


def find_manifests(repo: Path) -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = defaultdict(list)
    for p in walk_repo(repo):
        name = p.name.lower()
        if name.endswith(".txt") and name.startswith("requirements"):
            found["pypi_txt"].append(p)
        elif name == "pyproject.toml":
            found["pypi_pyproject"].append(p)
        elif name == "package-lock.json":
            found["npm_lock"].append(p)
        elif name == "package.json":
            found["npm_pkg"].append(p)
        elif name == "go.sum":
            found["go_sum"].append(p)
        elif name == "cargo.lock":
            found["cargo_lock"].append(p)
        elif name == "go.mod":
            found["go_mod"].append(p)
        elif name == "cargo.toml":
            found["cargo_toml"].append(p)
        elif name == "gemfile.lock":
            found["gem_lock"].append(p)
        elif name == "pom.xml":
            found["maven_pom"].append(p)
    return found


# -------------------------------------------------------------------------
# Parse manifests → list of (ecosystem, name, version, source_path)
# -------------------------------------------------------------------------

def parse_pypi_requirements(path: Path) -> list[tuple[str, str, str, Path]]:
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return out
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        m = PIN_PEP440.match(stripped)
        if m:
            out.append(("PyPI", m.group(1), m.group(2), path))
    return out


def parse_pypi_pyproject(path: Path) -> list[tuple[str, str, str, Path]]:
    out: list[tuple[str, str, str, Path]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return out
    # Heurística simple: cada línea "name==X.Y.Z" o "name = 'X.Y.Z'"
    for line in text.splitlines():
        m = re.match(r"^\s*['\"]?([A-Za-z0-9._\-]+)['\"]?\s*=\s*['\"]==?([0-9][\w.\-+]*)['\"]", line)
        if m:
            out.append(("PyPI", m.group(1), m.group(2), path))
        else:
            m2 = re.match(r"^\s*['\"]?([A-Za-z0-9._\-]+)\s*==\s*([0-9][\w.\-+]*)['\"]?\s*,?\s*$", line)
            if m2:
                out.append(("PyPI", m2.group(1), m2.group(2), path))
    return out


def parse_npm_lock(path: Path) -> list[tuple[str, str, str, Path]]:
    out: list[tuple[str, str, str, Path]] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    # npm 7+: packages: {"node_modules/foo": {version: ...}}
    packages = data.get("packages", {})
    for key, val in packages.items():
        if not key or key == "":
            continue
        name = key.split("node_modules/")[-1]
        version = val.get("version")
        if name and version:
            out.append(("npm", name, version, path))
    # Fallback npm 6: dependencies tree
    if not out:
        def walk_deps(node, parent=""):
            for nm, info in (node.get("dependencies") or {}).items():
                v = info.get("version")
                if v:
                    out.append(("npm", nm, v, path))
                walk_deps(info, nm)
        walk_deps(data)
    return out


def parse_go_sum(path: Path) -> list[tuple[str, str, str, Path]]:
    out: list[tuple[str, str, str, Path]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return out
    seen: set[tuple[str, str]] = set()
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1].startswith("v"):
            name, ver = parts[0], parts[1].rstrip("/go.mod")
            ver = ver.split("/")[0]
            if (name, ver) not in seen:
                seen.add((name, ver))
                out.append(("Go", name, ver, path))
    return out


def parse_cargo_lock(path: Path) -> list[tuple[str, str, str, Path]]:
    out: list[tuple[str, str, str, Path]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return out
    name = None
    for line in text.splitlines():
        s = line.strip()
        if s == "[[package]]":
            name = None
            continue
        m = re.match(r'^name\s*=\s*"([^"]+)"', s)
        if m:
            name = m.group(1)
            continue
        m = re.match(r'^version\s*=\s*"([^"]+)"', s)
        if m and name:
            out.append(("crates.io", name, m.group(1), path))
            name = None
    return out


def collect_dependencies(repo: Path) -> list[tuple[str, str, str, Path]]:
    manifests = find_manifests(repo)
    deps: list[tuple[str, str, str, Path]] = []
    for p in manifests.get("pypi_txt", []):
        deps.extend(parse_pypi_requirements(p))
    for p in manifests.get("pypi_pyproject", []):
        deps.extend(parse_pypi_pyproject(p))
    for p in manifests.get("npm_lock", []):
        deps.extend(parse_npm_lock(p))
    for p in manifests.get("go_sum", []):
        deps.extend(parse_go_sum(p))
    for p in manifests.get("cargo_lock", []):
        deps.extend(parse_cargo_lock(p))
    return deps


# -------------------------------------------------------------------------
# Cobertura — deps declaradas que quedaron FUERA del scan
# -------------------------------------------------------------------------

REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._\-]*)")


def _canon(name: str) -> str:
    """Canonicaliza nombre de paquete (PEP 503): case-insensitive, -/_ equivalentes."""
    return name.lower().replace("_", "-")


def _declared_in_requirements(path: Path) -> list[tuple[str, str, int]]:
    """(nombre, línea_cruda, nº_línea) de cada dep declarada en requirements*.txt,
    incluidas las que el scanner no puede resolver (sin pin, editable, URL)."""
    out: list[tuple[str, str, int]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return out
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith(("-e ", "--editable")):
            out.append(("(editable)", stripped, lineno))
            continue
        if stripped.startswith("-"):
            continue  # -r, -c, --hash… opciones, no deps
        if stripped.startswith(("git+", "http://", "https://", "./", "/", "file:")):
            out.append(("(url/path)", stripped, lineno))
            continue
        m = REQ_NAME_RE.match(stripped)
        if m:
            out.append((m.group(1), stripped, lineno))
    return out


def _declared_in_pyproject(path: Path) -> list[tuple[str, str]]:
    """(nombre, spec_cruda) de deps declaradas en pyproject.toml —
    [project.dependencies], optional-dependencies y [tool.poetry.*]."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover — Python < 3.11
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[str, str]] = []
    proj = data.get("project") or {}
    reqs: list[str] = list(proj.get("dependencies") or [])
    for lst in (proj.get("optional-dependencies") or {}).values():
        reqs.extend(lst or [])
    for raw in reqs:
        m = REQ_NAME_RE.match(str(raw).strip())
        if m:
            out.append((m.group(1), str(raw)))
    poetry = (data.get("tool") or {}).get("poetry") or {}
    dep_tables = [poetry.get("dependencies") or {}, poetry.get("dev-dependencies") or {}]
    for group in (poetry.get("group") or {}).values():
        dep_tables.append((group or {}).get("dependencies") or {})
    for table in dep_tables:
        for name, spec in table.items():
            if str(name).lower() == "python":
                continue
            if isinstance(spec, dict):
                spec = spec.get("version") or "(tabla compleja)"
            out.append((str(name), f'{name} = "{spec}"'))
    return out


def _count_package_json_deps(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return 0
    return len(data.get("dependencies") or {}) + len(data.get("devDependencies") or {})


def compute_coverage(repo: Path, deps: list[tuple[str, str, str, Path]]) -> dict:
    """Detecta dependencias declaradas que quedaron FUERA del scan.

    Compara lo declarado en cada manifest contra lo que los parsers realmente
    capturaron (deps) — por construcción reporta exactamente el gap del scan,
    sin duplicar la lógica de parseo. No modifica el comportamiento del scan;
    solo produce metadatos de cobertura para el reporte.
    """
    scanned_by_file: dict[Path, set[str]] = defaultdict(set)
    for _eco, name, _ver, p in deps:
        scanned_by_file[p].add(_canon(name))

    unpinned: list[dict] = []
    not_resolved: list[dict] = []
    manifests = find_manifests(repo)

    for p in manifests.get("pypi_txt", []):
        rel = p.relative_to(repo).as_posix()
        for name, raw, lineno in _declared_in_requirements(p):
            if _canon(name) not in scanned_by_file.get(p, set()):
                unpinned.append({"eco": "PyPI", "name": name, "spec": raw,
                                 "file": f"{rel}:{lineno}",
                                 "reason": "sin pin exacto o formato no soportado"})

    for p in manifests.get("pypi_pyproject", []):
        rel = p.relative_to(repo).as_posix()
        for name, raw in _declared_in_pyproject(p):
            if _canon(name) not in scanned_by_file.get(p, set()):
                unpinned.append({"eco": "PyPI", "name": name, "spec": raw,
                                 "file": rel,
                                 "reason": "sin pin exacto o formato no soportado"})

    npm_lock_dirs = {p.parent for p in manifests.get("npm_lock", [])}
    for p in manifests.get("npm_pkg", []):
        if p.parent in npm_lock_dirs:
            continue
        n = _count_package_json_deps(p)
        if n:
            not_resolved.append({"eco": "npm", "count": n,
                                 "file": p.relative_to(repo).as_posix(),
                                 "reason": "sin package-lock.json — versiones no resueltas"})

    go_sum_dirs = {p.parent for p in manifests.get("go_sum", [])}
    for p in manifests.get("go_mod", []):
        if p.parent not in go_sum_dirs:
            not_resolved.append({"eco": "Go", "count": 0,
                                 "file": p.relative_to(repo).as_posix(),
                                 "reason": "sin go.sum — módulos no resueltos"})

    cargo_lock_dirs = {p.parent for p in manifests.get("cargo_lock", [])}
    for p in manifests.get("cargo_toml", []):
        if p.parent not in cargo_lock_dirs:
            not_resolved.append({"eco": "crates.io", "count": 0,
                                 "file": p.relative_to(repo).as_posix(),
                                 "reason": "sin Cargo.lock — crates no resueltos"})

    outside = len(unpinned) + sum((x["count"] or 1) for x in not_resolved)
    return {"unpinned": unpinned, "not_resolved": not_resolved,
            "scanned_entries": len(deps), "outside_entries": outside}


# -------------------------------------------------------------------------
# Network — OSV.dev + CISA KEV
# -------------------------------------------------------------------------

def _post_json(url: str, body: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def _get_json(url: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def query_osv_batch(deps: list[tuple[str, str, str, Path]],
                    verbose: bool = False) -> dict[tuple[str, str, str], list[dict]]:
    """Query OSV.dev en batches de 1000. Devuelve {(eco, name, ver): [vulns...]}"""
    if not deps:
        return {}
    unique = list({(eco, n, v): None for eco, n, v, _ in deps}.keys())
    findings: dict[tuple[str, str, str], list[dict]] = {}
    BATCH = 1000
    for i in range(0, len(unique), BATCH):
        chunk = unique[i:i + BATCH]
        body = {"queries": [
            {"package": {"ecosystem": eco, "name": n}, "version": v}
            for eco, n, v in chunk
        ]}
        if verbose:
            print(f"  OSV.dev batch {i}-{i+len(chunk)}...", flush=True)
        try:
            resp = _post_json(OSV_BATCH_URL, body)
        except urllib.error.URLError as exc:
            print(f"ERROR: OSV.dev no responde: {exc}", file=sys.stderr)
            sys.exit(2)
        for key, result in zip(chunk, resp.get("results", [])):
            vulns = result.get("vulns") or []
            if vulns:
                findings[key] = vulns
    return findings


def enrich_vuln(vuln_id: str) -> dict:
    """Get details for a vuln ID from OSV.dev."""
    try:
        return _get_json(f"https://api.osv.dev/v1/vulns/{vuln_id}")
    except Exception:  # noqa: BLE001
        return {}


def get_cisa_kev(verbose: bool = False) -> set[str]:
    """Devuelve set de CVE IDs en CISA KEV. Cacheado 24h."""
    if KEV_CACHE.exists() and (time.time() - KEV_CACHE.stat().st_mtime) < KEV_TTL_SECONDS:
        if verbose:
            print("  CISA KEV: cache hit", flush=True)
        try:
            data = json.loads(KEV_CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
    else:
        if verbose:
            print("  CISA KEV: descargando...", flush=True)
        try:
            data = _get_json(CISA_KEV_URL)
            KEV_CACHE.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: CISA KEV no disponible: {exc}", file=sys.stderr)
            data = {}
    return {v.get("cveID") for v in data.get("vulnerabilities", []) if v.get("cveID")}


# -------------------------------------------------------------------------
# Analysis
# -------------------------------------------------------------------------

def severity_of(vuln: dict) -> tuple[str, str]:
    """Returns (label, cvss_score_str)."""
    sev = vuln.get("severity") or []
    cvss_score = ""
    label = "unknown"
    if sev:
        for s in sev:
            if "score" in s:
                cvss_score = str(s["score"])
                break
    # database_specific.severity (GHSA convention)
    db = vuln.get("database_specific") or {}
    if "severity" in db:
        label = str(db["severity"]).lower()
    # ecosystem_specific severity
    if label == "unknown":
        eco = vuln.get("ecosystem_specific") or {}
        if "severity" in eco:
            label = str(eco["severity"]).lower()
    # heuristic from CVSS score
    if label == "unknown" and cvss_score:
        try:
            score = float(cvss_score.split("CVSS:")[-1].split("/")[0]) if "CVSS:" in cvss_score else float(cvss_score)
            if score >= 9.0:
                label = "critical"
            elif score >= 7.0:
                label = "high"
            elif score >= 4.0:
                label = "medium"
            elif score > 0:
                label = "low"
        except Exception:  # noqa: BLE001
            pass
    return label, cvss_score


def first_fixed_version(vuln: dict, ecosystem: str, package: str) -> str | None:
    for affected in vuln.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("ecosystem") != ecosystem or pkg.get("name") != package:
            continue
        for r in affected.get("ranges", []):
            for ev in r.get("events", []):
                if "fixed" in ev:
                    return ev["fixed"]
    return None


def extract_cve_ids(vuln: dict) -> list[str]:
    out: list[str] = []
    if vuln.get("id", "").startswith("CVE-"):
        out.append(vuln["id"])
    for alias in vuln.get("aliases", []) or []:
        if alias.startswith("CVE-"):
            out.append(alias)
    return out


# -------------------------------------------------------------------------
# Extra layers (v2) — EPSS, SAST, container, secrets, workflows, hadolint, typosquat
# -------------------------------------------------------------------------

EPSS_API = "https://api.first.org/data/v1/epss"
POPULAR_PYPI = {
    "requests", "urllib3", "pip", "setuptools", "wheel", "numpy", "pandas",
    "django", "flask", "fastapi", "sqlalchemy", "pydantic", "pytest",
    "boto3", "click", "rich", "httpx", "aiohttp", "uvicorn", "tornado",
    "celery", "redis", "pymongo", "openai", "anthropic", "langchain",
    "langgraph", "tensorflow", "torch", "scikit-learn", "matplotlib",
}


def has_tool(name: str) -> bool:
    return shutil.which(name) is not None


# ---- Capa: EPSS (Exploit Prediction Scoring System) -----------------------

def fetch_epss(cve_ids: list[str], verbose: bool = False) -> dict[str, dict]:
    """POST a EPSS API. Devuelve {cve_id: {epss, percentile, date}}."""
    if not cve_ids:
        return {}
    result: dict[str, dict] = {}
    # EPSS soporta hasta ~100 CVEs por GET. Hacemos chunks.
    for i in range(0, len(cve_ids), 50):
        chunk = cve_ids[i:i + 50]
        url = f"{EPSS_API}?cve={','.join(chunk)}"
        try:
            data = _get_json(url, timeout=15)
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  EPSS: error {exc}", flush=True)
            return result
        for d in data.get("data", []):
            cve = d.get("cve")
            if cve:
                result[cve] = {
                    "epss": float(d.get("epss", 0)),
                    "percentile": float(d.get("percentile", 0)),
                    "date": d.get("date"),
                }
    return result


# ---- Capa: SAST (Bandit) --------------------------------------------------

def run_bandit(repo: Path, verbose: bool = False) -> list[dict]:
    """Ejecuta bandit -r en src/ del repo. Devuelve hallazgos."""
    # Detectar bandit: binario directo o módulo Python instalado
    bandit_cmd: list[str] | None = None
    if has_tool("bandit"):
        bandit_cmd = ["bandit"]
    else:
        try:
            r = subprocess.run([sys.executable, "-m", "bandit", "--version"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                bandit_cmd = [sys.executable, "-m", "bandit"]
        except Exception:  # noqa: BLE001
            pass
    if bandit_cmd is None:
        if verbose:
            print("  bandit: no instalado (pip install bandit)", flush=True)
        return []
    targets = []
    for cand in ("src", "cases", "shared", "scripts", "app", "backend"):
        p = repo / cand
        if p.is_dir():
            targets.append(str(p))
    if not targets:
        targets = [str(repo)]
    # Excluir vendor/deps/build/test dirs (falsos positivos masivos)
    exclude_patterns = [
        "*/.deps/*", "*/.venv/*", "*/venv/*", "*/site-packages/*",
        "*/node_modules/*", "*/vendor/*", "*/dist/*", "*/build/*",
        "*/__pycache__/*", "*/.pytest_cache/*", "*/tests/*",
        "*/test_*.py", "*_test.py",
    ]
    cmd = bandit_cmd + ["-r", "-f", "json", "-q",
                        "-x", ",".join(exclude_patterns)] + targets
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=repo, timeout=300)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"  bandit: {exc}", flush=True)
        return []
    if not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return []
    findings = []
    for r in data.get("results", []):
        sev = r.get("issue_severity", "LOW").lower()
        conf = r.get("issue_confidence", "LOW").lower()
        findings.append({
            "layer": "sast",
            "severity": sev,
            "confidence": conf,
            "test_id": r.get("test_id"),
            "title": r.get("test_name"),
            "summary": r.get("issue_text", "")[:300],
            "file": r.get("filename"),
            "line": r.get("line_number"),
            "code": (r.get("code") or "")[:200],
            "ref": r.get("more_info"),
        })
    return findings


# ---- Capa: Container scan (trivy / grype) ---------------------------------

def run_container_scan(repo: Path, verbose: bool = False) -> list[dict]:
    """trivy fs . (preferido) o grype dir:. — escanea OS layer + deps no pinneadas."""
    cmd = None
    tool = None
    if has_tool("trivy"):
        tool = "trivy"
        cmd = ["trivy", "fs", "--format", "json", "--severity",
               "HIGH,CRITICAL", "--quiet", str(repo)]
    elif has_tool("grype"):
        tool = "grype"
        cmd = ["grype", f"dir:{repo}", "-o", "json", "-q"]
    else:
        return []
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"  {tool}: {exc}", flush=True)
        return []
    if not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return []
    findings: list[dict] = []
    if tool == "trivy":
        for res in data.get("Results", []):
            target = res.get("Target", "?")
            for v in res.get("Vulnerabilities", []) or []:
                findings.append({
                    "layer": "container",
                    "tool": "trivy",
                    "severity": v.get("Severity", "UNKNOWN").lower(),
                    "cve": v.get("VulnerabilityID"),
                    "pkg": v.get("PkgName"),
                    "version": v.get("InstalledVersion"),
                    "fixed": v.get("FixedVersion"),
                    "title": v.get("Title", v.get("VulnerabilityID")),
                    "summary": (v.get("Description") or "")[:300],
                    "target": target,
                    "ref": (v.get("PrimaryURL") or ""),
                })
    else:  # grype
        for m in data.get("matches", []):
            v = m.get("vulnerability", {})
            a = m.get("artifact", {})
            findings.append({
                "layer": "container",
                "tool": "grype",
                "severity": v.get("severity", "Unknown").lower(),
                "cve": v.get("id"),
                "pkg": a.get("name"),
                "version": a.get("version"),
                "fixed": ", ".join((v.get("fix") or {}).get("versions", [])) or None,
                "title": v.get("id"),
                "summary": (v.get("description") or "")[:300],
                "target": a.get("locations", [{}])[0].get("path"),
                "ref": v.get("dataSource"),
            })
    return findings


# ---- Capa: Secrets (detect-secrets / gitleaks) ----------------------------

def run_secrets_scan(repo: Path, verbose: bool = False) -> list[dict]:
    findings: list[dict] = []
    if has_tool("gitleaks"):
        try:
            proc = subprocess.run(
                ["gitleaks", "detect", "--no-banner", "--report-format", "json",
                 "--report-path", "-", "--source", str(repo)],
                capture_output=True, text=True, timeout=300,
            )
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  gitleaks: {exc}", flush=True)
            return []
        if proc.stdout.strip():
            try:
                data = json.loads(proc.stdout)
            except Exception:  # noqa: BLE001
                data = []
            for r in data or []:
                findings.append({
                    "layer": "secrets",
                    "tool": "gitleaks",
                    "severity": "high",
                    "title": r.get("Description", r.get("RuleID")),
                    "file": r.get("File"),
                    "line": r.get("StartLine"),
                    "summary": f"Rule: {r.get('RuleID')}; commit {r.get('Commit', '?')[:8]}",
                    "ref": "https://github.com/gitleaks/gitleaks",
                })
        return findings
    # Fallback detect-secrets (requiere baseline)
    if has_tool("detect-secrets"):
        baseline = repo / ".secrets.baseline"
        if not baseline.exists():
            if verbose:
                print("  detect-secrets: sin baseline (.secrets.baseline) — saltando", flush=True)
            return []
        try:
            proc = subprocess.run(
                ["detect-secrets", "scan", "--baseline", str(baseline), str(repo)],
                capture_output=True, text=True, timeout=300,
            )
        except Exception:  # noqa: BLE001
            return []
        if proc.stdout.strip():
            try:
                data = json.loads(proc.stdout)
            except Exception:  # noqa: BLE001
                data = {}
            for fpath, items in (data.get("results") or {}).items():
                for it in items:
                    findings.append({
                        "layer": "secrets",
                        "tool": "detect-secrets",
                        "severity": "high",
                        "title": it.get("type"),
                        "file": fpath,
                        "line": it.get("line_number"),
                        "summary": f"Hash: {it.get('hashed_secret', '')[:12]}…",
                        "ref": "https://github.com/Yelp/detect-secrets",
                    })
    return findings


# ---- Capa: Workflows GHA (zizmor) -----------------------------------------

def run_workflow_scan(repo: Path, verbose: bool = False) -> list[dict]:
    wf_dir = repo / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    if not has_tool("zizmor"):
        return []
    try:
        proc = subprocess.run(
            ["zizmor", "--format", "json", str(wf_dir)],
            capture_output=True, text=True, timeout=180,
        )
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"  zizmor: {exc}", flush=True)
        return []
    if not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return []
    findings = []
    items = data if isinstance(data, list) else data.get("findings", [])
    for r in items:
        findings.append({
            "layer": "workflows",
            "tool": "zizmor",
            "severity": str(r.get("determinations", {}).get("severity",
                              r.get("severity", "medium"))).lower(),
            "title": r.get("ident", r.get("id")),
            "summary": (r.get("desc") or r.get("description") or "")[:300],
            "file": (r.get("locations", [{}])[0].get("symbolic", {}).get("key", {}) or {}).get("Local", "?"),
            "ref": "https://github.com/woodruffw/zizmor",
        })
    return findings


# ---- Capa: Dockerfile (hadolint) ------------------------------------------

def run_hadolint(repo: Path, verbose: bool = False) -> list[dict]:
    if not has_tool("hadolint"):
        return []
    findings: list[dict] = []
    for df in repo.rglob("Dockerfile"):
        if any(part in EXCLUDE_DIRS for part in df.parts):
            continue
        try:
            proc = subprocess.run(
                ["hadolint", "--format", "json", "--no-color", str(df)],
                capture_output=True, text=True, timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  hadolint {df.name}: {exc}", flush=True)
            continue
        if not proc.stdout.strip():
            continue
        try:
            data = json.loads(proc.stdout)
        except Exception:  # noqa: BLE001
            continue
        for r in data:
            findings.append({
                "layer": "dockerfile",
                "tool": "hadolint",
                "severity": r.get("level", "info").lower().replace("warning", "medium").replace("error", "high"),
                "title": r.get("code"),
                "summary": r.get("message", "")[:300],
                "file": str(df.relative_to(repo).as_posix()),
                "line": r.get("line"),
                "ref": f"https://github.com/hadolint/hadolint/wiki/{r.get('code')}",
            })
    return findings


# ---- Helpers: extracción de fix/remediation desde texto libre -------------

REMEDIATION_PATTERNS = [
    (re.compile(r"(?:upgrade|update|bump)\s+(?:to|a)\s+([0-9][\w.\-+]*)", re.I), "Upgrade a {0}"),
    (re.compile(r"(?:fixed|patched|resolved)\s+in\s+(?:version\s+)?v?([0-9][\w.\-+]*)", re.I), "Parchado en {0}"),
    (re.compile(r"versi[oó]n\s+([0-9][\w.\-+]*)\s+o\s+(?:superior|posterior|nueva)", re.I), "Versión {0}+"),
    (re.compile(r"workaround[:\s]+([^.]+)\.", re.I), "Workaround: {0}"),
    (re.compile(r"mitigation[:\s]+([^.]+)\.", re.I), "Mitigación: {0}"),
    (re.compile(r"disable\s+([\w.\- ]+)\s+(?:feature|option|setting)", re.I), "Deshabilitar {0}"),
    (re.compile(r"set\s+([\w.\-]+)\s*=\s*([\w.\-]+)", re.I), "Configurar {0}={1}"),
    (re.compile(r"remove\s+(?:and\s+replace|or\s+replace)\s+(?:with\s+)?([\w.\-@/]+)", re.I), "Reemplazar por {0}"),
    (re.compile(r"reemplazar\s+por\s+([\w.\-@/]+)", re.I), "Reemplazar por {0}"),
]


def extract_remediation(text: str) -> str | None:
    """Extrae heurísticamente la acción de remediación de un texto libre."""
    if not text:
        return None
    for pattern, template in REMEDIATION_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return template.format(*m.groups())
            except IndexError:
                return template.format(m.group(1))
    return None


# ---- Capa: CISA Cybersecurity Advisories (RSS) + GHSA recent --------------

CISA_ADVISORIES_RSS = "https://www.cisa.gov/cybersecurity-advisories/all.xml"
NVD_RECENT_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _fetch_rss(url: str, timeout: int = 30) -> list[dict]:
    """Fetch RSS/Atom feed and return list of {title, link, description, pubDate}."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    items: list[dict] = []
    # Naive XML parsing — items separados por <item>...</item> o <entry>...</entry>
    for block_re in (r"<item>(.*?)</item>", r"<entry>(.*?)</entry>"):
        for block in re.findall(block_re, raw, re.DOTALL):
            def grab(tag: str, b=block) -> str:
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", b, re.DOTALL)
                if not m:
                    return ""
                txt = m.group(1).strip()
                # Strip CDATA
                m2 = re.match(r"<!\[CDATA\[(.*?)\]\]>", txt, re.DOTALL)
                if m2:
                    txt = m2.group(1)
                # Strip simple HTML tags
                return re.sub(r"<[^>]+>", " ", txt).strip()
            items.append({
                "title": grab("title"),
                "link": grab("link") or re.search(r'<link[^>]*href="([^"]+)"', block, re.DOTALL).group(1) if re.search(r'<link[^>]*href="([^"]+)"', block, re.DOTALL) else "",
                "description": grab("description") or grab("summary") or grab("content"),
                "pubDate": grab("pubDate") or grab("published") or grab("updated"),
            })
    return items


def run_news_layer(deps: list[tuple[str, str, str, Path]],
                   verbose: bool = False, days: int = 30) -> list[dict]:
    """CISA Cybersecurity Advisories + GHSA recent. Cruza con TUS paquetes por nombre."""
    findings: list[dict] = []
    dep_names = {n.lower() for _, n, _, _ in deps}
    cutoff = time.time() - days * 86400

    # CISA
    cisa_items = _fetch_rss(CISA_ADVISORIES_RSS, timeout=20)
    if verbose:
        print(f"  CISA Advisories: {len(cisa_items)} items recibidos", flush=True)
    for it in cisa_items:
        title = it.get("title", "")
        desc = it.get("description", "")
        # Filtrar por fecha (parse simple)
        pub = it.get("pubDate", "")
        try:
            pub_ts = time.mktime(time.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S"))
            if pub_ts < cutoff:
                continue
        except Exception:  # noqa: BLE001
            pass
        # Cruzar con paquetes del repo. Sólo cuenta si:
        # 1) el package es un nombre técnico (no palabra inglesa común)
        # 2) Y aparece con word boundary
        # 3) Y el advisory menciona contexto Python/PyPI/pip OR el name es muy específico
        AMBIGUOUS_NAMES = {  # nombres que también son palabras comunes
            "click", "requests", "rich", "typer", "future", "more",
            "test", "name", "data", "time", "type", "object", "string",
            "request", "session", "model", "config", "settings", "task",
            "next", "first", "last", "common", "core", "tools", "utils",
            "build", "install", "update", "version", "table", "list",
        }
        full = (title + " " + desc).lower()
        is_python_context = bool(re.search(
            r"\b(python|pypi|pip\s+install|wheel|requirements\.txt|setup\.py)\b",
            full,
        ))
        matched_pkgs = []
        for n in dep_names:
            if len(n) < 5 or n in AMBIGUOUS_NAMES:
                # Nombres cortos o ambiguos: sólo si hay contexto Python explícito
                if not is_python_context:
                    continue
            if re.search(rf"(?<![a-z0-9_\-]){re.escape(n)}(?![a-z0-9_\-])", full):
                matched_pkgs.append(n)
        if not matched_pkgs:
            continue
        sev = "high" if any(w in full for w in ("critical", "rce", "remote code", "exploit")) else "medium"
        findings.append({
            "layer": "news",
            "tool": "CISA",
            "severity": sev,
            "title": title,
            "summary": desc[:400],
            "pkg": ", ".join(matched_pkgs[:3]),
            "ref": it.get("link"),
            "pubDate": pub,
            "fix": extract_remediation(desc),
        })

    # GHSA recent (vía gh CLI si está)
    if shutil.which("gh"):
        try:
            proc = subprocess.run(
                ["gh", "api", "/advisories?per_page=100&sort=published&direction=desc"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
                advisories = json.loads(proc.stdout)
                if verbose:
                    print(f"  GHSA recent: {len(advisories)} items", flush=True)
                for adv in advisories[:100]:
                    pub = adv.get("published_at") or ""
                    try:
                        pub_ts = time.mktime(time.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S"))
                        if pub_ts < cutoff:
                            continue
                    except Exception:  # noqa: BLE001
                        pass
                    affected_pkgs = []
                    for vuln in adv.get("vulnerabilities") or []:
                        p = ((vuln.get("package") or {}).get("name") or "").lower()
                        if p and p in dep_names:
                            affected_pkgs.append(p)
                    if not affected_pkgs:
                        continue
                    desc = adv.get("description") or ""
                    findings.append({
                        "layer": "news",
                        "tool": "GHSA",
                        "severity": (adv.get("severity") or "medium").lower(),
                        "title": adv.get("summary") or adv.get("ghsa_id"),
                        "summary": desc[:400],
                        "cve": (adv.get("cve_id") or adv.get("ghsa_id")),
                        "pkg": ", ".join(affected_pkgs[:3]),
                        "ref": adv.get("html_url"),
                        "pubDate": pub,
                        "fix": extract_remediation(desc) or
                               f"Upgrade — ver fix en {adv.get('html_url')}",
                    })
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  GHSA recent: {exc}", flush=True)
    return findings


# ---- Capa: Recent (filtra OSV findings por fecha de publicación) ----------

def filter_recent_osv(findings: dict, days: int = 30) -> list[dict]:
    """Devuelve hallazgos OSV publicados en últimos N días."""
    cutoff = time.time() - days * 86400
    recent: list[dict] = []
    for (eco, name, ver), vulns in findings.items():
        for v in vulns:
            pub = v.get("published") or v.get("modified") or ""
            try:
                pub_ts = time.mktime(time.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S"))
                if pub_ts < cutoff:
                    continue
            except Exception:  # noqa: BLE001
                continue
            cves = extract_cve_ids(v)
            recent.append({
                "layer": "recent",
                "tool": "OSV-date-filter",
                "severity": severity_of(v)[0],
                "title": (cves[0] if cves else v.get("id", "?")),
                "summary": (v.get("summary") or v.get("details") or "")[:300],
                "pkg": f"{name}",
                "version": ver,
                "fixed": first_fixed_version(v, eco, name),
                "ref": (v.get("references") or [{}])[0].get("url"),
                "pubDate": pub,
                "fix": f"Bump a {first_fixed_version(v, eco, name)}" if first_fixed_version(v, eco, name) else None,
            })
    return recent


# ---- Capa: Sonatype OSS Index (paquetes maliciosos + vulns) ---------------

OSS_INDEX_URL = "https://ossindex.sonatype.org/api/v3/component-report"


def run_pypi_malware(deps: list[tuple[str, str, str, Path]],
                     verbose: bool = False) -> list[dict]:
    """Sonatype OSS Index: detecta paquetes retirados / malicious.

    Requiere SONATYPE_OSSI_USER + SONATYPE_OSSI_TOKEN (free signup en
    https://ossindex.sonatype.org/user/register). Sin credenciales, retorna [].
    """
    user = os.getenv("SONATYPE_OSSI_USER", "").strip()
    token = os.getenv("SONATYPE_OSSI_TOKEN", "").strip()
    pypi_deps = [(n, v) for eco, n, v, _ in deps if eco == "PyPI"]
    if not pypi_deps:
        return []
    unique = list({(n, v): None for n, v in pypi_deps}.keys())
    findings: list[dict] = []
    import base64
    auth_header = None
    if user and token:
        auth_header = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()
    # Sonatype: max 128 coordinates por request
    for i in range(0, len(unique), 128):
        chunk = unique[i:i + 128]
        body = {"coordinates": [f"pkg:pypi/{n}@{v}" for n, v in chunk]}
        headers = {"Content-Type": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        try:
            req = urllib.request.Request(
                OSS_INDEX_URL, data=json.dumps(body).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                if verbose:
                    print("  Sonatype OSS Index: requiere SONATYPE_OSSI_USER + "
                          "SONATYPE_OSSI_TOKEN (free signup en ossindex.sonatype.org). "
                          "Saltando capa.", flush=True)
            elif verbose:
                print(f"  Sonatype OSS Index: HTTP {exc.code}", flush=True)
            return findings
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"  Sonatype OSS Index: {exc}", flush=True)
            return findings
        items = data if isinstance(data, list) else []
        for entry in items:
            vulns = entry.get("vulnerabilities") or []
            if not vulns:
                continue
            coord = entry.get("coordinates", "")
            # parse pkg:pypi/name@version
            m = re.match(r"pkg:pypi/([^@]+)@(.+)", coord)
            if not m:
                continue
            name, ver = m.group(1), m.group(2)
            for vuln in vulns:
                cvss = vuln.get("cvssScore")
                sev = "critical" if cvss and cvss >= 9.0 else \
                      "high" if cvss and cvss >= 7.0 else \
                      "medium" if cvss and cvss >= 4.0 else "low"
                desc = vuln.get("description", "")
                findings.append({
                    "layer": "pypi-malware",
                    "tool": "Sonatype OSS Index",
                    "severity": sev,
                    "title": vuln.get("title", "?"),
                    "summary": desc[:400],
                    "cve": vuln.get("cve"),
                    "pkg": name,
                    "version": ver,
                    "ref": vuln.get("reference"),
                    "fix": extract_remediation(desc) or "Revisar referencia oficial",
                })
    return findings


# ---- Capa: Typosquat heuristic (PyPI) -------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(min(cur[j] + 1, prev[j + 1] + 1, prev[j] + (ca != cb)))
        prev = cur
    return prev[-1]


def detect_typosquats(deps: list[tuple[str, str, str, Path]],
                      verbose: bool = False) -> list[dict]:
    findings: list[dict] = []
    pypi_names = {n.lower() for eco, n, _, _ in deps if eco == "PyPI"}
    for name in pypi_names:
        if name in POPULAR_PYPI:
            continue
        for popular in POPULAR_PYPI:
            d = _levenshtein(name, popular)
            if 0 < d <= 1 and abs(len(name) - len(popular)) <= 1:
                findings.append({
                    "layer": "typosquat",
                    "tool": "heuristic-levenshtein",
                    "severity": "medium",
                    "title": f"posible typosquat: `{name}` vs `{popular}`",
                    "summary": (f"El paquete `{name}` difiere en {d} carácter del "
                                f"paquete popular `{popular}`. Verifica intencionalidad."),
                    "ref": "https://owasp.org/www-community/attacks/Typosquatting",
                })
                break
    return findings


# -------------------------------------------------------------------------
# Report
# -------------------------------------------------------------------------

def build_report(
    deps: list[tuple[str, str, str, Path]],
    findings: dict[tuple[str, str, str], list[dict]],
    kev_set: set[str],
    repo: Path,
    applied: list[str],
    min_severity: str = "low",
    epss_scores: dict[str, dict] | None = None,
    extra_layers: dict[str, list[dict]] | None = None,
    coverage: dict | None = None,
) -> str:
    epss_scores = epss_scores or {}
    extra_layers = extra_layers or {}
    min_rank = SEVERITY_RANK.get(min_severity, 1)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ecosystems = sorted({d[0] for d in deps})

    # Flatten findings per package+vuln
    rows: list[dict] = []
    for (eco, name, ver), vulns in findings.items():
        for v in vulns:
            sev_label, cvss = severity_of(v)
            if SEVERITY_RANK.get(sev_label, 0) < min_rank:
                continue
            cves = extract_cve_ids(v)
            in_kev = any(c in kev_set for c in cves)
            fixed = first_fixed_version(v, eco, name)
            sources_paths = sorted({str(p[3].relative_to(repo).as_posix())
                                    for p in deps if (p[0], p[1], p[2]) == (eco, name, ver)})
            rows.append({
                "eco": eco, "name": name, "version": ver,
                "vuln_id": v.get("id", "?"),
                "cves": cves, "kev": in_kev,
                "severity": sev_label, "cvss": cvss,
                "summary": (v.get("summary") or v.get("details") or "")[:300],
                "fixed": fixed,
                "refs": [r.get("url") for r in (v.get("references") or []) if r.get("url")][:5],
                "sources": sources_paths,
            })

    # Sort by (KEV desc, severity desc, name)
    rows.sort(key=lambda r: (not r["kev"], -SEVERITY_RANK.get(r["severity"], 0), r["name"]))

    counts = defaultdict(int)
    for r in rows:
        counts[r["severity"]] += 1
    kev_count = sum(1 for r in rows if r["kev"])

    # Línea de cobertura para el resumen ejecutivo
    coverage_line = None
    if coverage is not None:
        cov_outside = coverage.get("outside_entries", 0)
        cov_scanned = coverage.get("scanned_entries", len(deps))
        cov_total = cov_scanned + cov_outside
        if cov_outside:
            cov_pct = round(100 * cov_scanned / cov_total) if cov_total else 0
            coverage_line = (
                f"- **⚠ Cobertura del scan de deps:** {cov_scanned} de {cov_total} entradas "
                f"declaradas ({cov_pct}%) — **{cov_outside} FUERA del scan** "
                f"(ver sección 🔍 Cobertura)")
        else:
            coverage_line = ("- **Cobertura del scan de deps:** completa — todas las "
                             "dependencias declaradas tienen versión exacta resuelta")

    extra_total = sum(len(v) for v in extra_layers.values())
    md = [
        f"# Auditoría de seguridad — `{repo.name}` — {now}",
        "",
        "Generado por skill `security-audit` v2 (multi-layer). "
        "Cruza dependencias y código contra fuentes oficiales: OSV.dev (NVD + GHSA + PyPA + "
        "Go vuln DB + RustSec + etc.) · CISA KEV (explotación activa) · EPSS (probabilidad "
        "de exploit) · Bandit SAST · trivy/grype (container) · zizmor (GHA workflows) · "
        "hadolint (Dockerfile) · gitleaks/detect-secrets · typosquat heuristic.",
        "",
        "## Resumen ejecutivo",
        "",
        f"- **Ecosistemas auditados:** {', '.join(ecosystems) or 'ninguno detectado'}",
        f"- **Dependencias revisadas:** {len({(d[0], d[1], d[2]) for d in deps})} únicas "
        f"(total entradas: {len(deps)})",
        *([coverage_line] if coverage_line else []),
        f"- **Vulnerabilidades en deps (OSV):** {len(rows)} "
        f"(critical: {counts['critical']}, high: {counts['high']}, "
        f"medium: {counts['medium']+counts['moderate']}, low: {counts['low']}, "
        f"unknown: {counts['unknown']})",
        f"- **En CISA KEV (explotación activa):** {kev_count}",
        f"- **Hallazgos en capas extra:** {extra_total - len(extra_layers.get('__blocked__', []))} "
        f"({', '.join(f'{k}: {len(v)}' for k, v in extra_layers.items() if v and not k.startswith('__')) or 'ninguna activa'})",
        "",
    ]

    # ---- Sección Cobertura (antes del early-return: "0 vulns" con baja
    # cobertura es exactamente el caso que NO debe quedar oculto) ----
    if coverage and (coverage.get("unpinned") or coverage.get("not_resolved")):
        md.append("## 🔍 Cobertura del scan de dependencias")
        md.append("")
        md.append("La capa OSV solo audita versiones **exactas** resueltas. Las siguientes "
                  "dependencias declaradas quedaron **fuera del scan** y pueden contener "
                  "CVEs no reflejadas en este reporte:")
        md.append("")
        md.append("| Dependencia | Declarada como | Archivo | Motivo |")
        md.append("|---|---|---|---|")
        unpinned_items = coverage.get("unpinned", [])
        for u in unpinned_items[:50]:
            md.append(f"| `{u['name']}` | `{u['spec']}` | `{u['file']}` | {u['reason']} |")
        for nr in coverage.get("not_resolved", []):
            what = f"({nr['count']} deps)" if nr.get("count") else "(módulos)"
            md.append(f"| {what} | — | `{nr['file']}` | {nr['reason']} |")
        if len(unpinned_items) > 50:
            md.append("")
            md.append(f"_…y {len(unpinned_items) - 50} más (truncado a 50)._")
        md.append("")
        md.append("> **Sugerencia:** pinnea con `pip freeze` / `pip-compile`, o añade el "
                  "lockfile del ecosistema (`package-lock.json`, `poetry.lock`, `go.sum`, "
                  "`Cargo.lock`) para llevar la cobertura a 100%. Un resultado de "
                  '"0 vulnerabilidades" solo aplica a lo efectivamente escaneado.')
        md.append("")

    if not rows and not any(extra_layers.values()):
        md.append("## ✅ Sin vulnerabilidades por encima del umbral configurado")
        md.append("")
        return "\n".join(md)

    if not rows:
        md.append("## ✅ Sin vulnerabilidades en dependencias (capa OSV)")
        md.append("")
        md.append("Continúa con los hallazgos de capas extra abajo.")
        md.append("")

    sections = [
        ("🔴 Hallazgos críticos con explotación activa (CISA KEV)", lambda r: r["kev"] and r["severity"] == "critical"),
        ("🔴 Hallazgos críticos", lambda r: r["severity"] == "critical" and not r["kev"]),
        ("🟠 Hallazgos altos en CISA KEV", lambda r: r["kev"] and r["severity"] == "high"),
        ("🟠 Hallazgos altos", lambda r: r["severity"] == "high" and not r["kev"]),
        ("🟡 Hallazgos medios", lambda r: r["severity"] in ("medium", "moderate")),
        ("⚪ Hallazgos bajos / sin clasificar", lambda r: r["severity"] in ("low", "unknown")),
    ]
    for title, predicate in sections:
        sec_rows = [r for r in rows if predicate(r)]
        if not sec_rows:
            continue
        md.append(f"## {title}")
        md.append("")
        for r in sec_rows:
            cve_str = " · ".join(r["cves"]) or r["vuln_id"]
            kev_badge = " · **CISA KEV ✓**" if r["kev"] else ""
            cvss_str = f" · CVSS {r['cvss']}" if r["cvss"] else ""
            md.append(f"### {cve_str} — `{r['name']}` `{r['version']}` ({r['eco']})")
            md.append("")
            md.append(f"- **Severidad:** {r['severity'].upper()}{cvss_str}{kev_badge}")
            # EPSS scoring (exploit probability)
            epss_info = next((epss_scores.get(c) for c in r["cves"] if c in epss_scores), None)
            if epss_info:
                pct = round(epss_info["percentile"] * 100, 1)
                prob = round(epss_info["epss"] * 100, 2)
                md.append(f"- **EPSS:** {prob}% probabilidad de explotación en 30 días "
                          f"(percentil {pct})")
            if r["summary"]:
                md.append(f"- **Resumen:** {r['summary']}")
            if r["fixed"]:
                md.append(f"- **Fix disponible:** bump a `{r['fixed']}`")
            else:
                md.append("- **Fix disponible:** ⚠ sin versión parchada — mitigar manualmente")
            md.append(f"- **Archivos afectados:** " +
                      ", ".join(f"`{s}`" for s in r["sources"]))
            if r["refs"]:
                md.append("- **Referencias:**")
                for u in r["refs"]:
                    md.append(f"  - {u}")
            md.append("")

    # ---- Secciones por capa extra (SAST, container, secrets, workflows, hadolint, typosquat) ----
    LAYER_TITLES = {
        "recent": "🆕 Capa Recent — CVEs OSV publicados en últimos 30 días",
        "news": "📰 Capa News — CISA Advisories + GitHub Security Advisories recientes",
        "pypi-malware": "☠ Capa PyPI Malware — Sonatype OSS Index (retirados/malicious)",
        "sast": "🧠 Capa SAST — Bandit (vulnerabilidades en TU código)",
        "container": "🐳 Capa Container — trivy/grype (OS layer + deps no pinneadas)",
        "secrets": "🔑 Capa Secrets — gitleaks/detect-secrets",
        "workflows": "⚙ Capa Workflows GHA — zizmor (injection, perms, unpinned)",
        "dockerfile": "📦 Capa Dockerfile — hadolint",
        "typosquat": "🪞 Capa Typosquat — heurística Levenshtein vs PyPI populares",
    }
    sev_rank_extra = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "unknown": 0}
    for layer_key, title in LAYER_TITLES.items():
        items = extra_layers.get(layer_key) or []
        items = [i for i in items if sev_rank_extra.get(i.get("severity", "unknown"), 0) >= min_rank]
        if not items:
            continue
        md.append(f"## {title}")
        md.append("")
        items.sort(key=lambda x: -sev_rank_extra.get(x.get("severity", "unknown"), 0))
        for it in items[:50]:  # Top 50 por capa para no inundar
            sev = (it.get("severity") or "unknown").upper()
            ttl = it.get("title") or it.get("cve") or it.get("test_id") or "?"
            md.append(f"### `{sev}` — {ttl}")
            md.append("")
            if it.get("cve"):
                md.append(f"- **CVE:** {it['cve']}")
            if it.get("pkg") and it.get("version"):
                fix_note = f" → fix `{it['fixed']}`" if it.get("fixed") else ""
                md.append(f"- **Paquete:** `{it['pkg']}` `{it['version']}`{fix_note}")
            if it.get("file"):
                loc = it["file"]
                if it.get("line"):
                    loc += f":{it['line']}"
                md.append(f"- **Ubicación:** `{loc}`")
            if it.get("target"):
                md.append(f"- **Target:** `{it['target']}`")
            if it.get("summary"):
                md.append(f"- **Detalle:** {it['summary']}")
            if it.get("ref"):
                md.append(f"- **Referencia:** {it['ref']}")
            md.append("")
        if len(items) > 50:
            md.append(f"_…y {len(items) - 50} hallazgos más en esta capa (truncado)._")
            md.append("")

    if applied or extra_layers.get("__blocked__"):
        md.append("## ✅ Acciones aplicadas")
        md.append("")
        for line in applied:
            md.append(f"- {line}")
        blocked_items = extra_layers.get("__blocked__") or []
        if blocked_items:
            md.append("")
            md.append("### ❌ Bumps bloqueados (revertidos por --verify)")
            md.append("")
            for line in blocked_items:
                md.append(f"- {line.get('what', line) if isinstance(line, dict) else line}")
        md.append("")

    pendings = [r for r in rows if not r["fixed"]]
    if pendings:
        md.append("## ⚠ Pendientes sin fix upstream")
        md.append("")
        for r in pendings:
            cve_str = " · ".join(r["cves"]) or r["vuln_id"]
            md.append(f"- {cve_str} — `{r['name']}` `{r['version']}` ({r['eco']}): "
                      "evaluar mitigación o reemplazo del paquete.")
        md.append("")

    # ---- Plan de Remediación (transversal) ----
    remediation_items: list[dict] = []
    for r in rows:
        if r.get("fixed"):
            remediation_items.append({
                "severity": r["severity"],
                "kev": r["kev"],
                "what": f"Bump `{r['name']}=={r['version']}` → `{r['name']}=={r['fixed']}`",
                "for": " · ".join(r["cves"]) or r["vuln_id"],
                "in": ", ".join(r["sources"]),
            })
    for layer_key, items in extra_layers.items():
        for it in items:
            if it.get("fix"):
                pkg_info = f"`{it.get('pkg', '?')}`" if it.get("pkg") else ""
                loc = it.get("file") or it.get("target") or ""
                remediation_items.append({
                    "severity": it.get("severity", "unknown"),
                    "kev": False,
                    "what": it["fix"],
                    "for": it.get("title") or it.get("cve") or layer_key,
                    "in": f"{pkg_info} {loc}".strip(),
                })
    if remediation_items:
        # ordenar: KEV primero, luego severity desc
        remediation_items.sort(key=lambda x: (
            not x["kev"], -sev_rank_extra.get(x["severity"], 0),
        ))
        md.append("## 🎯 Plan de Remediación (transversal)")
        md.append("")
        md.append("Checklist agregando el `fix` recomendado de cada capa, ordenado por "
                  "(CISA KEV → severidad). Marca cada item al aplicarlo:")
        md.append("")
        for it in remediation_items[:100]:
            sev_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡",
                         "moderate": "🟡", "low": "⚪", "unknown": "⚪"}.get(it["severity"], "⚪")
            kev_tag = " **[CISA KEV]**" if it["kev"] else ""
            md.append(f"- [ ] {sev_emoji} **{it['what']}**{kev_tag}")
            md.append(f"  - Resuelve: `{it['for']}`")
            if it["in"]:
                md.append(f"  - En: {it['in']}")
        if len(remediation_items) > 100:
            md.append(f"")
            md.append(f"_…y {len(remediation_items) - 100} acciones más (truncado a 100)._")
        md.append("")

    md.append("## Cómo reproducir")
    md.append("")
    md.append("```bash")
    md.append("python ~/.claude/skills/security-audit/security_audit.py")
    md.append("```")
    md.append("")
    return "\n".join(md)


# -------------------------------------------------------------------------
# Apply fixes
# -------------------------------------------------------------------------

def apply_fix_pypi(manifest: Path, name: str, old: str, new: str) -> bool:
    text = manifest.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"(^|\n)({re.escape(name)})==({re.escape(old)})(\s|$)")
    new_text, n = pattern.subn(rf"\1\2=={new}\4", text)
    if n > 0:
        manifest.write_text(new_text, encoding="utf-8")
        return True
    return False


def _minimal_fix_version(vulns: list[dict], eco: str, name: str, current: str) -> str | None:
    """Devuelve la versión MÁS PEQUEÑA que arregla todos los vulns (minimal blast radius)."""
    candidates: list[str] = []
    for v in vulns:
        fx = first_fixed_version(v, eco, name)
        if fx and _version_greater(fx, current):
            candidates.append(fx)
    if not candidates:
        return None
    # ordenar ascendente y tomar el mayor de los mínimos requeridos
    candidates.sort(key=lambda s: tuple(int(x) for x in re.split(r"[.\-+]", s) if x.isdigit()))
    return candidates[-1]  # el mínimo que cubre TODOS los vulns


def _run_verify(manifest: Path, test_cmd: str, verbose: bool = False) -> tuple[bool, str]:
    """Tras un bump, instala deps y corre tests. Retorna (ok, message)."""
    backend_dir = manifest.parent
    # 1) pip install -r (en el dir del manifest)
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", manifest.name],
            cwd=backend_dir, capture_output=True, text=True, timeout=300,
        )
        if r1.returncode != 0:
            return False, f"pip install falló: {r1.stderr[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"pip install error: {exc}"
    # 2) tests (default: pytest -x -q)
    cmd = test_cmd.split() if test_cmd else [sys.executable, "-m", "pytest", "-x", "-q"]
    try:
        r2 = subprocess.run(cmd, cwd=backend_dir, capture_output=True,
                            text=True, timeout=600)
        if r2.returncode != 0:
            return False, f"tests fallaron: {r2.stdout[-300:] or r2.stderr[-300:]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"tests error: {exc}"
    return True, "ok"


def apply_fixes(findings: dict[tuple[str, str, str], list[dict]],
                deps: list[tuple[str, str, str, Path]],
                verify: bool = False, test_cmd: str = "",
                verbose: bool = False) -> tuple[list[str], list[str]]:
    """Aplica bumps. Devuelve (applied, blocked).

    Si verify=True: tras cada bump corre pip install + tests; si falla revierte.
    Si verify=False: aplica todos los bumps sin verificación.
    """
    applied: list[str] = []
    blocked: list[str] = []
    by_key: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for eco, n, v, p in deps:
        by_key[(eco, n, v)].append(p)

    for (eco, name, ver), vulns in findings.items():
        best_fix = _minimal_fix_version(vulns, eco, name, ver)
        if not best_fix:
            continue
        if eco != "PyPI":
            blocked.append(
                f"⚠ {eco} `{name}` {ver} → {best_fix}: regeneración manual del lockfile requerida"
            )
            continue
        for manifest in by_key[(eco, name, ver)]:
            if not (manifest.name.endswith(".txt") or manifest.name.endswith(".in")):
                continue
            # Backup
            original = manifest.read_bytes()
            if not apply_fix_pypi(manifest, name, ver, best_fix):
                continue
            if verify:
                if verbose:
                    print(f"    verificando bump {name}=={ver}→{best_fix} en "
                          f"{manifest.relative_to(REPO).as_posix()}...", flush=True)
                ok, msg = _run_verify(manifest, test_cmd, verbose)
                if not ok:
                    manifest.write_bytes(original)  # REVERT
                    blocked.append(
                        f"❌ `{manifest.relative_to(REPO).as_posix()}`: "
                        f"`{name}=={ver}` → `{name}=={best_fix}` REVERTIDO ({msg})"
                    )
                    continue
            applied.append(
                f"✅ `{manifest.relative_to(REPO).as_posix()}`: "
                f"`{name}=={ver}` → `{name}=={best_fix}`"
                + (" (verificado: tests OK)" if verify else "")
            )
    return applied, blocked


def _version_greater(a: str, b: str) -> bool:
    """Comparación naive de versiones semver-ish."""
    try:
        ta = tuple(int(x) for x in re.split(r"[.\-+]", a) if x.isdigit())
        tb = tuple(int(x) for x in re.split(r"[.\-+]", b) if x.isdigit())
        return ta > tb
    except Exception:  # noqa: BLE001
        return a > b


# -------------------------------------------------------------------------
# Git integration
# -------------------------------------------------------------------------

def run_git(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=REPO)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def git_commit_and_push(report_path: Path, applied: list[str]) -> str | None:
    if not (REPO / ".git").exists():
        print("No es un repo git — saltando git/PR.", file=sys.stderr)
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    branch = f"claude/security-audit-{today}"
    run_git(["checkout", "-b", branch])
    # Stage el reporte
    run_git(["add", str(report_path.relative_to(REPO))])
    # Stage los manifests modificados
    rc, status = run_git(["status", "--porcelain"])
    for line in status.splitlines():
        if line[3:].endswith(("requirements.txt", "requirements.in", "pyproject.toml")):
            run_git(["add", line[3:].strip()])
    summary = f"fix(security): bump deps vulnerables ({len(applied)} cambios)"
    body = "Audit auto-generado por skill security-audit. Ver reporte adjunto."
    msg = f"{summary}\n\n{body}\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
    rc, out = run_git(["commit", "-m", msg])
    if rc != 0:
        print(f"git commit falló: {out}", file=sys.stderr)
        return None
    rc, out = run_git(["push", "-u", "origin", branch])
    if rc != 0:
        print(f"git push falló: {out}", file=sys.stderr)
        return branch
    return branch


def create_pr(branch: str, applied_count: int) -> str | None:
    title = f"fix(security): security-audit auto-bump ({applied_count} deps)"
    body = "PR generado por skill `security-audit`. Ver `SECURITY_AUDIT_*.md` en la raíz."
    proc = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body],
        capture_output=True, text=True, cwd=REPO,
    )
    if proc.returncode != 0:
        print(f"gh pr create falló: {proc.stderr}", file=sys.stderr)
        return None
    pr_url = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else None
    subprocess.run(["gh", "pr", "merge", "--squash", "--auto"],
                   capture_output=True, text=True, cwd=REPO)
    return pr_url


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Audita seguridad de un repo.")
    parser.add_argument("--apply", action="store_true",
                        help="Aplicar bumps a la primera versión segura disponible.")
    parser.add_argument("--git", action="store_true",
                        help="Crear rama git + commit con los cambios.")
    parser.add_argument("--pr", action="store_true",
                        help="Crear PR vía gh CLI (auto-merge squash).")
    parser.add_argument("--ecosystem", action="append", default=None,
                        help="Filtrar a un ecosistema (PyPI, npm, Go, ...). Repetir para varios.")
    parser.add_argument("--min-severity", default="low",
                        choices=["low", "medium", "high", "critical"])
    parser.add_argument("--out-dir", default=".",
                        help="Carpeta para el reporte MD (default: raíz del repo).")
    parser.add_argument(
        "--layers", default="osv,kev,epss,recent,news,typosquat",
        help="Capas a ejecutar (csv). Opciones: osv, kev, epss, recent, news, "
             "pypi-malware, sast, container, secrets, workflows, dockerfile, "
             "typosquat, all. Default: las que no requieren binarios externos.",
    )
    parser.add_argument(
        "--recent-days", type=int, default=30,
        help="Ventana de tiempo para capas `recent` y `news` (default: 30 días).",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Tras cada --apply: corre pip install + tests; revierte si falla.",
    )
    parser.add_argument(
        "--test-cmd", default="",
        help="Comando custom de tests (default: 'python -m pytest -x -q').",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    layers = {x.strip().lower() for x in args.layers.split(",") if x.strip()}
    if "all" in layers:
        layers = {"osv", "kev", "epss", "recent", "news", "pypi-malware",
                  "sast", "container", "secrets", "workflows", "dockerfile",
                  "typosquat"}

    print(f"Security audit — repo: {REPO}")
    deps = collect_dependencies(REPO)
    coverage = compute_coverage(REPO, deps)
    if args.ecosystem:
        eco_set = set(args.ecosystem)
        deps = [d for d in deps if d[0] in eco_set]
        coverage["unpinned"] = [u for u in coverage["unpinned"] if u["eco"] in eco_set]
        coverage["not_resolved"] = [n for n in coverage["not_resolved"] if n["eco"] in eco_set]
        coverage["outside_entries"] = len(coverage["unpinned"]) + sum(
            (n["count"] or 1) for n in coverage["not_resolved"])
        coverage["scanned_entries"] = len(deps)

    counts_by_eco = defaultdict(int)
    for d in deps:
        counts_by_eco[d[0]] += 1
    if not counts_by_eco:
        if coverage["outside_entries"]:
            print(f"  ⚠ 0 dependencias escaneables, pero {coverage['outside_entries']} "
                  "declaradas SIN pin exacto o sin lockfile.")
            print("    El scan NO cubre nada de este repo — pinnea versiones o añade "
                  "lockfiles y vuelve a correr.")
            for u in coverage["unpinned"][:10]:
                print(f"      - {u['spec']}  ({u['file']})")
            for n in coverage["not_resolved"][:10]:
                print(f"      - {n['file']}  ({n['reason']})")
            return 1
        print("No se detectaron manifests. Verifica que estés en la raíz del repo.")
        return 0
    print("  Detectados:", ", ".join(f"{c} {e}" for e, c in counts_by_eco.items()))
    if coverage["outside_entries"]:
        print(f"  ⚠ Cobertura: {coverage['outside_entries']} dependencia(s) declaradas "
              "FUERA del scan (sin pin exacto o sin lockfile) — detalle en el reporte")

    findings: dict = {}
    kev_set: set[str] = set()
    if "osv" in layers:
        findings = query_osv_batch(deps, verbose=args.verbose)
        n_vulns = sum(len(v) for v in findings.values())
        print(f"  [OSV] {n_vulns} vulns en {len(findings)} dep-versiones únicas")
    if "kev" in layers:
        kev_set = get_cisa_kev(verbose=args.verbose)
        print(f"  [CISA KEV] {len(kev_set)} CVEs activos en catálogo")

    # ---- EPSS scoring sobre los CVEs OSV encontrados ----
    epss_scores: dict[str, dict] = {}
    if "epss" in layers and findings:
        all_cves: list[str] = []
        for vulns in findings.values():
            for v in vulns:
                all_cves.extend(extract_cve_ids(v))
        all_cves = list(set(all_cves))
        if all_cves:
            epss_scores = fetch_epss(all_cves, verbose=args.verbose)
            print(f"  [EPSS] scoring para {len(epss_scores)}/{len(all_cves)} CVEs")

    # ---- Capas extra ----
    extra_layers: dict[str, list[dict]] = {}
    layer_runners = {
        "recent":       ("OSV-recent",    lambda: filter_recent_osv(findings, args.recent_days)),
        "news":         ("CISA/GHSA",     lambda: run_news_layer(deps, args.verbose, args.recent_days)),
        "pypi-malware": ("Sonatype OSSI", lambda: run_pypi_malware(deps, args.verbose)),
        "sast":         ("Bandit",        lambda: run_bandit(REPO, args.verbose)),
        "container":    ("trivy/grype",   lambda: run_container_scan(REPO, args.verbose)),
        "secrets":      ("gitleaks/det.", lambda: run_secrets_scan(REPO, args.verbose)),
        "workflows":    ("zizmor",        lambda: run_workflow_scan(REPO, args.verbose)),
        "dockerfile":   ("hadolint",      lambda: run_hadolint(REPO, args.verbose)),
        "typosquat":    ("typosquat",     lambda: detect_typosquats(deps, args.verbose)),
    }
    EXTERNAL = {"sast", "container", "secrets", "workflows", "dockerfile",
                "news", "pypi-malware"}
    for key, (tool_name, runner) in layer_runners.items():
        if key not in layers:
            continue
        items = runner()
        extra_layers[key] = items
        if items:
            print(f"  [{tool_name}] {len(items)} hallazgos")
        elif args.verbose:
            if key in EXTERNAL:
                print(f"  [{tool_name}] sin hallazgos o herramienta no instalada")
            else:
                print(f"  [{tool_name}] sin hallazgos")

    applied: list[str] = []
    blocked: list[str] = []
    if args.apply:
        applied, blocked = apply_fixes(findings, deps, verify=args.verify,
                                       test_cmd=args.test_cmd, verbose=args.verbose)
        print(f"  Aplicados: {len(applied)} cambios"
              + (f", BLOQUEADOS: {len(blocked)}" if blocked else ""))

    if blocked:
        extra_layers["__blocked__"] = blocked
    report = build_report(deps, findings, kev_set, REPO, applied, args.min_severity,
                          epss_scores=epss_scores, extra_layers=extra_layers,
                          coverage=coverage)
    n_vulns = sum(len(v) for v in findings.values()) + sum(len(v) for v in extra_layers.values())
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = (REPO / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"SECURITY_AUDIT_{today}.md"
    report_path.write_text(report, encoding="utf-8")
    try:
        shown_path = report_path.relative_to(REPO).as_posix()
    except ValueError:  # --out-dir fuera del repo
        shown_path = str(report_path)
    print(f"  Reporte: {shown_path}")

    if args.git and applied:
        branch = git_commit_and_push(report_path, applied)
        if branch and args.pr:
            pr = create_pr(branch, len(applied))
            if pr:
                print(f"  PR: {pr}")

    return 1 if n_vulns else 0


if __name__ == "__main__":
    sys.exit(main())
