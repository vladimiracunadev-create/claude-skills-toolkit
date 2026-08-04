#!/usr/bin/env python3
"""
version_probe — vuelve determinista la regla crítica de `version-bump`:
distinguir un marcador de versión ACTUAL (hay que bumpearlo) de una
referencia HISTÓRICA (hay que conservarla).

Un `grep` de la versión vieja devuelve las dos cosas mezcladas, y ahí nace el
error más caro del proceso: o se olvida un badge y la landing sigue anunciando
la versión anterior, o se reescribe una entrada de changelog y se rompe la
trazabilidad para siempre.

Este script clasifica cada aparición en tres cubos y, con `--verify`, ejecuta
la prueba de fuego: ningún marcador ACTUAL puede seguir mostrando la versión
vieja, y la nueva debe estar presente donde toca.

Uso:
    python version_probe.py                              # detecta versión canónica y clasifica
    python version_probe.py --old 0.2.0                  # clasifica esa versión
    python version_probe.py --verify --old 0.2.0 --new 0.3.0
    python version_probe.py --json

Agnóstico del stack (Rust, Node, Python, Go, .NET, Java, o sin gestor).
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
    "__pycache__", "vendor", "vendor_py", ".venv", "venv", "coverage",
}
_TEXT_EXT = {
    ".md", ".txt", ".toml", ".json", ".yml", ".yaml", ".cfg", ".ini",
    ".py", ".rs", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".kt",
    ".cs", ".csproj", ".xml", ".html", ".sh", ".ps1", ".rb", ".php",
    ".gradle", ".props", ".nuspec", ".env", ".conf", "",
}
_MAX_BYTES = 2_000_000

CURRENT = "ACTUAL"
HISTORIC = "HISTORICO"
AMBIGUOUS = "AMBIGUO"

# Ficheros cuyo propósito ES registrar la historia. Salvo la sección
# "Unreleased", todo lo que hay dentro es historia por definición.
CHANGELOG_NAMES = re.compile(r"(CHANGELOG|HISTORY|RELEASES|NEWS)", re.IGNORECASE)

# Manifests: el campo de versión es, por definición, el estado actual.
MANIFEST_NAMES = {
    "package.json", "package-lock.json", "pyproject.toml", "Cargo.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "Directory.Build.props",
    "VERSION", "version.txt", "Chart.yaml", "composer.json", "setup.py",
    "setup.cfg", "pubspec.yaml", "go.mod", "*.csproj", "*.nuspec",
}

# Señales de que la línea habla del PASADO.
HISTORIC_HINTS = re.compile(
    r"\b("
    r"entregad[ao]|completad[ao]|publicad[ao]|liberad[ao]|cerrad[ao]|"
    r"released?|shipped|landed|"
    r"added\s+in|fixed\s+in|introduc(?:ed|id[ao])\s+(?:in|en)|"
    r"since\s+v?\d|desde\s+la\s+v|deprecated\s+in|removed\s+in|"
    r"changelog|historial|migrat(?:ed|ion)\s+from"
    r")\b",
    re.IGNORECASE,
)

# Señales INEQUÍVOCAS de estado presente. Se comprueban ANTES que las de
# pasado: un badge de versión es estado actual aunque enlace al CHANGELOG, y
# esa palabra en la URL no lo convierte en historia.
STRONG_CURRENT_HINTS = re.compile(
    r"("
    r"img\.shields\.io|badge/|"
    r"__version__|\bVERSION\s*=|\"version\"\s*:|^\s*version\s*=|<Version>|"
    r"--version|app_version|appVersion|versionName|version_string"
    r")",
    re.IGNORECASE,
)

# Señales más débiles de estado presente: se comprueban DESPUÉS de las de
# pasado, porque "entregado en v1.2 (versión actual 1.3)" es historia.
CURRENT_HINTS = re.compile(
    r"("
    r"versi[oó]n\s+actual|current\s+version|latest\s+stable|versi[oó]n\s+base|"
    r"actualmente|en\s+curso"
    r")",
    re.IGNORECASE,
)


@dataclass
class Hit:
    path: str
    line_no: int
    line: str
    kind: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "path": self.path, "line": self.line_no, "text": self.line.strip()[:200],
            "kind": self.kind, "reason": self.reason,
        }


@dataclass
class Probe:
    root: Path
    old: str = ""
    new: str = ""
    canonical: list[tuple[str, str]] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)

    def by(self, kind: str) -> list[Hit]:
        return [h for h in self.hits if h.kind == kind]


def rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


def _skip(p: Path, root: Path) -> bool:
    try:
        parts = p.relative_to(root).parts
    except ValueError:
        return True
    for part in parts[:-1]:
        if part in _VENDOR or (part.startswith(".") and part not in (".", ".github")):
            return True
    return p.suffix.lower() not in _TEXT_EXT


def _read(p: Path) -> str:
    try:
        if p.stat().st_size > _MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ------------------------------------------------------- versión canónica

def find_canonical(root: Path) -> list[tuple[str, str]]:
    """Versión declarada por cada manifest de la raíz. Es la fuente de verdad."""
    out: list[tuple[str, str]] = []

    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(_read(pkg))
            if isinstance(data, dict) and data.get("version"):
                out.append(("package.json", str(data["version"])))
        except json.JSONDecodeError:
            pass

    pp = root / "pyproject.toml"
    if pp.is_file():
        text = _read(pp)
        ver = None
        if tomllib:
            try:
                d = tomllib.loads(text)
                ver = (d.get("project") or {}).get("version") or (
                    ((d.get("tool") or {}).get("poetry") or {}).get("version")
                )
            except Exception:
                ver = None
        if not ver:
            m = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', text)
            ver = m.group(1) if m else None
        if ver:
            out.append(("pyproject.toml", ver))

    cg = root / "Cargo.toml"
    if cg.is_file():
        m = re.search(r'(?ms)^\[package\].*?^\s*version\s*=\s*"([^"]+)"', _read(cg))
        if m:
            out.append(("Cargo.toml", m.group(1)))

    for name in ("VERSION", "version.txt"):
        f = root / name
        if f.is_file():
            lines = [ln.strip() for ln in _read(f).splitlines() if ln.strip()]
            if lines:
                out.append((name, lines[0]))

    for csproj in sorted(root.glob("*.csproj")) + sorted(root.glob("*/*.csproj")):
        m = re.search(r"<Version>([^<]+)</Version>", _read(csproj))
        if m:
            out.append((rel(root, csproj), m.group(1).strip()))

    pom = root / "pom.xml"
    if pom.is_file():
        m = re.search(r"<version>([^<]+)</version>", _read(pom))
        if m:
            out.append(("pom.xml", m.group(1).strip()))

    return out


# ---------------------------------------------------------- clasificación

def classify(path: Path, root: Path, line_no: int, line: str,
             in_unreleased: bool) -> tuple[str, str]:
    name = path.name
    relpath = rel(root, path)

    # 1. Changelog: es el registro de la historia. Todo es histórico salvo la
    #    sección "Unreleased", que sí describe el estado que viene.
    if CHANGELOG_NAMES.search(name):
        if in_unreleased:
            return CURRENT, "sección Unreleased del changelog"
        return HISTORIC, "entrada de changelog — la historia no se reescribe"

    # 2. Manifest con campo de versión: estado actual por definición.
    if name in MANIFEST_NAMES or path.suffix in (".csproj", ".nuspec"):
        if re.search(r'(version|Version)\s*[=:>]', line):
            return CURRENT, "campo de versión de un manifest"

    # 3. Señales inequívocas de presente: badge, campo de versión, `--version`.
    #    Van primero porque un badge que enlaza a CHANGELOG.md sigue siendo
    #    estado actual — la palabra en la URL no lo vuelve historia.
    if STRONG_CURRENT_HINTS.search(line):
        return CURRENT, "marcador inequívoco de estado actual (badge o campo de versión)"

    # 4. Señales explícitas de pasado.
    if HISTORIC_HINTS.search(line):
        return HISTORIC, "la línea habla en pasado"

    # 5. Señales más débiles de presente.
    if CURRENT_HINTS.search(line):
        return CURRENT, "etiqueta de estado actual"

    # 6. Encabezado de sección con la versión: en ROADMAP suele ser estado,
    #    en cualquier otro doc suele ser historia. Sin más contexto, ambiguo.
    if re.match(r"^\s{0,3}#{1,6}\s", line):
        if re.search(r"ROADMAP|PLAN", relpath, re.IGNORECASE):
            return CURRENT, "encabezado de roadmap (estado planificado)"
        return AMBIGUOUS, "encabezado con versión — revisar si titula historia o estado"

    return AMBIGUOUS, "sin señal clara de pasado ni de presente"


def scan(root: Path, old: str) -> list[Hit]:
    pattern = re.compile(r"(?<![\w.])v?" + re.escape(old) + r"(?![\w.])")
    unreleased_re = re.compile(r"^\s{0,3}#{1,6}\s*\[?\s*(unreleased|sin\s+publicar|próxima)", re.IGNORECASE)
    version_heading_re = re.compile(r"^\s{0,3}#{1,6}\s*\[?\s*v?\d+\.\d+")

    hits: list[Hit] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or _skip(p, root):
            continue
        text = _read(p)
        if not text or old not in text:
            continue
        in_unreleased = False
        for i, line in enumerate(text.splitlines(), start=1):
            if CHANGELOG_NAMES.search(p.name):
                if unreleased_re.match(line):
                    in_unreleased = True
                elif version_heading_re.match(line):
                    in_unreleased = False
            if not pattern.search(line):
                continue
            kind, reason = classify(p, root, i, line, in_unreleased)
            hits.append(Hit(path=rel(root, p), line_no=i, line=line, kind=kind, reason=reason))
    return hits


# ---------------------------------------------------------------- salida

def render(pr: Probe, verify: bool) -> str:
    lines = [f"version_probe — repo: {pr.root}", ""]

    if pr.canonical:
        lines.append("Versión canónica declarada por los manifests:")
        for src, ver in pr.canonical:
            lines.append(f"  · {src:<28} {ver}")
        distinct = {v for _, v in pr.canonical}
        if len(distinct) > 1:
            lines.append(f"  ⚠ DRIFT: los manifests no coinciden entre sí: {', '.join(sorted(distinct))}")
        lines.append("")

    lines.append(f"Apariciones de «{pr.old}»: {len(pr.hits)}")
    lines.append("")

    for kind, mark, blurb in (
        (CURRENT, "→", "SE BUMPEA — marcadores del estado actual"),
        (HISTORIC, "🔒", "SE CONSERVA — referencias históricas"),
        (AMBIGUOUS, "?", "REVISAR A MANO — sin señal concluyente"),
    ):
        group = pr.by(kind)
        lines.append(f"{kind} · {blurb} ({len(group)})")
        if not group:
            lines.append("  (ninguna)")
        for h in group[:40]:
            lines.append(f"  {mark} {h.path}:{h.line_no}  — {h.reason}")
            lines.append(f"      {h.line.strip()[:110]}")
        if len(group) > 40:
            lines.append(f"  … y {len(group) - 40} más")
        lines.append("")

    if verify:
        stale = pr.by(CURRENT)
        lines.append("PRUEBA DE FUEGO")
        if stale:
            lines.append(f"  ✗ {len(stale)} marcador(es) ACTUAL siguen mostrando {pr.old}:")
            for h in stale[:20]:
                lines.append(f"      {h.path}:{h.line_no}")
        else:
            lines.append(f"  ✓ Ningún marcador ACTUAL conserva {pr.old}.")
        if pr.new:
            found_new = sum(1 for _ in scan(pr.root, pr.new))
            if found_new:
                lines.append(f"  ✓ {pr.new} aparece en {found_new} sitio(s).")
            else:
                lines.append(f"  ✗ {pr.new} no aparece en ninguna parte del repo.")
        lines.append("")

    amb = pr.by(AMBIGUOUS)
    if amb:
        lines.append(
            f"⚠ {len(amb)} aparición(es) sin clasificar automáticamente. El script no "
            "adivina:\n  revísalas antes de dar el bump por cerrado."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="version_probe",
        description="Clasifica cada aparición de una versión en ACTUAL / HISTORICO / AMBIGUO.",
    )
    ap.add_argument("--old", help="Versión a clasificar. Por defecto, la canónica de los manifests.")
    ap.add_argument("--new", help="Versión nueva — con --verify comprueba que ya esté presente.")
    ap.add_argument("--verify", action="store_true",
                    help="Prueba de fuego: falla si algún marcador ACTUAL conserva la versión vieja.")
    ap.add_argument("--json", action="store_true", help="Salida JSON.")
    args = ap.parse_args(argv)

    root = Path.cwd()
    pr = Probe(root=root, new=args.new or "")
    pr.canonical = find_canonical(root)

    if args.old:
        pr.old = args.old
    elif pr.canonical:
        pr.old = pr.canonical[0][1]
    else:
        sys.stderr.write(
            "ERROR: no se detectó versión canónica en ningún manifest. Indica --old explícitamente.\n"
        )
        return 2

    pr.hits = scan(root, pr.old)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "old": pr.old,
            "new": pr.new,
            "canonical": [{"source": s, "version": v} for s, v in pr.canonical],
            "current": [h.as_dict() for h in pr.by(CURRENT)],
            "historic": [h.as_dict() for h in pr.by(HISTORIC)],
            "ambiguous": [h.as_dict() for h in pr.by(AMBIGUOUS)],
        }, indent=2, ensure_ascii=False))
    else:
        print(render(pr, verify=args.verify))

    if args.verify and pr.by(CURRENT):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
