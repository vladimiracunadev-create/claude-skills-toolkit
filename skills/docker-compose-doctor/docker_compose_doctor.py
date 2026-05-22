#!/usr/bin/env python3
"""
docker-compose-doctor — análisis estático de archivos compose.yml.

Detecta 6 clases de problemas que el schema oficial no captura:
1. Puertos host duplicados entre servicios (error)
2. Servicios sin healthcheck (warning)
3. depends_on simple cuando el target tiene healthcheck (warning)
4. Imágenes con :latest o sin tag (warning)
5. Volúmenes nombrados declarados pero no referenciados (warning)
6. env_file apuntando a archivo inexistente (error)

Trabaja sobre Path.cwd(). Cero deps externas más allá de pyyaml.

Exit codes:
  0 — sin hallazgos o solo warnings
  1 — al menos un error
  2 — error de invocación
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: pyyaml requerido. Instala con: pip install pyyaml\n")
    sys.exit(2)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


COMPOSE_GLOBS = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")
MAX_SEARCH_DEPTH = 3


@dataclass
class Finding:
    severity: str  # "error" | "warning"
    check: str
    message: str
    service: str | None = None
    line: int | None = None
    suggestion: str | None = None


@dataclass
class Report:
    file: str
    services_count: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


def find_compose_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for depth in range(MAX_SEARCH_DEPTH + 1):
        pattern = "/".join(["*"] * depth) if depth else ""
        for name in COMPOSE_GLOBS:
            glob = f"{pattern}/{name}" if pattern else name
            found.extend(root.glob(glob))
    seen: set[Path] = set()
    unique = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique


def load_compose(path: Path) -> tuple[dict[str, Any], dict[str, int]]:
    """Carga compose y un mapa heurístico nombre→línea."""
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        sys.stderr.write(f"ERROR: YAML malformado en {path}: {exc}\n")
        sys.exit(2)

    line_map: dict[str, int] = {}
    for idx, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":"):
            key = stripped[:-1].strip()
            line_map.setdefault(key, idx)
    return data, line_map


def _parse_port_mapping(port: Any) -> tuple[str | None, str]:
    """Devuelve (host_port, raw) o (None, raw) si no se puede extraer."""
    if isinstance(port, int):
        return None, str(port)
    if isinstance(port, str):
        raw = port
        if "/" in port:
            port = port.split("/", 1)[0]
        if ":" in port:
            parts = port.split(":")
            host = parts[-2] if len(parts) >= 2 else None
            if host and ("." in host or host.lower() == "host"):
                return parts[-2] if len(parts) >= 3 else None, raw
            return host, raw
        return None, raw
    if isinstance(port, dict):
        published = port.get("published")
        return (str(published) if published is not None else None), str(port)
    return None, str(port)


def check_duplicate_ports(services: dict[str, Any], lines: dict[str, int]) -> list[Finding]:
    findings: list[Finding] = []
    port_owners: dict[str, list[tuple[str, str]]] = {}
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for port in svc.get("ports", []) or []:
            host_port, raw = _parse_port_mapping(port)
            if host_port:
                port_owners.setdefault(host_port, []).append((svc_name, raw))
    for host_port, owners in port_owners.items():
        if len(owners) > 1:
            names = ", ".join(f"'{n}'" for n, _ in owners)
            details = "  ".join(f"{n}: {r!r}" for n, r in owners)
            findings.append(Finding(
                severity="error",
                check="duplicate_ports",
                message=f"Puerto host {host_port} duplicado entre servicios {names}\n    {details}",
            ))
    return findings


def check_missing_healthchecks(services: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        if "healthcheck" not in svc:
            hc = svc.get("healthcheck") or {}
            if isinstance(hc, dict) and hc.get("disable"):
                continue
            findings.append(Finding(
                severity="warning",
                check="missing_healthcheck",
                service=svc_name,
                message=f"Servicio '{svc_name}' sin healthcheck — depends_on no podrá esperar a service_healthy",
            ))
    return findings


def check_depends_on_simple(services: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    has_hc = {n for n, s in services.items() if isinstance(s, dict) and "healthcheck" in s}
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        deps = svc.get("depends_on")
        if not deps:
            continue
        if isinstance(deps, list):
            for target in deps:
                if target in has_hc:
                    findings.append(Finding(
                        severity="warning",
                        check="depends_on_simple",
                        service=svc_name,
                        message=(
                            f"Servicio '{svc_name}' depende de '{target}' "
                            f"(que tiene healthcheck) con depends_on simple"
                        ),
                        suggestion=(
                            "depends_on:\n"
                            f"          {target}:\n"
                            "            condition: service_healthy"
                        ),
                    ))
        elif isinstance(deps, dict):
            for target, cfg in deps.items():
                if not isinstance(cfg, dict):
                    continue
                if target in has_hc and cfg.get("condition") not in {"service_healthy", "service_completed_successfully"}:
                    cond = cfg.get("condition", "<missing>")
                    findings.append(Finding(
                        severity="warning",
                        check="depends_on_condition",
                        service=svc_name,
                        message=(
                            f"Servicio '{svc_name}' depende de '{target}' "
                            f"(que tiene healthcheck) con condition: {cond}"
                        ),
                        suggestion="condition: service_healthy",
                    ))
    return findings


def check_image_tags(services: dict[str, Any], lines: dict[str, int]) -> list[Finding]:
    findings: list[Finding] = []
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        image = svc.get("image")
        if not image or not isinstance(image, str):
            continue
        if "${" in image:
            continue
        ref = image.split("@", 1)[0]
        if ":" not in ref.split("/")[-1]:
            findings.append(Finding(
                severity="warning",
                check="image_no_tag",
                service=svc_name,
                line=lines.get(svc_name),
                message=f"Imagen '{image}' en servicio '{svc_name}' sin tag — pinnea a una versión explícita",
            ))
            continue
        tag = ref.split(":")[-1]
        if tag == "latest":
            findings.append(Finding(
                severity="warning",
                check="image_latest",
                service=svc_name,
                line=lines.get(svc_name),
                message=f"Imagen '{image}' en servicio '{svc_name}' usa ':latest' — pinnea a versión explícita",
            ))
    return findings


def check_orphan_volumes(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    declared = data.get("volumes") or {}
    if not isinstance(declared, dict):
        return findings
    referenced: set[str] = set()
    for svc in (data.get("services") or {}).values():
        if not isinstance(svc, dict):
            continue
        for vol in svc.get("volumes", []) or []:
            if isinstance(vol, str):
                name = vol.split(":", 1)[0]
                if name and not name.startswith((".", "/", "~")):
                    referenced.add(name)
            elif isinstance(vol, dict):
                source = vol.get("source")
                if source and vol.get("type") == "volume":
                    referenced.add(source)
    for name in declared.keys():
        if name not in referenced:
            findings.append(Finding(
                severity="warning",
                check="orphan_volume",
                message=f"Volumen '{name}' declarado pero no referenciado por ningún servicio",
            ))
    return findings


def check_env_files(services: dict[str, Any], compose_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    base = compose_path.parent
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        env_file = svc.get("env_file")
        if not env_file:
            continue
        entries = env_file if isinstance(env_file, list) else [env_file]
        for entry in entries:
            if isinstance(entry, dict):
                path_str = entry.get("path")
                required = entry.get("required", True)
            else:
                path_str = entry
                required = True
            if not path_str or not required:
                continue
            target = (base / path_str).resolve()
            if not target.exists():
                findings.append(Finding(
                    severity="error",
                    check="missing_env_file",
                    service=svc_name,
                    message=f"env_file inexistente en servicio '{svc_name}': {path_str}",
                ))
    return findings


def diagnose(path: Path) -> Report:
    data, lines = load_compose(path)
    services = data.get("services") or {}
    if not isinstance(services, dict):
        services = {}
    report = Report(file=str(path), services_count=len(services))
    report.findings.extend(check_duplicate_ports(services, lines))
    report.findings.extend(check_missing_healthchecks(services))
    report.findings.extend(check_depends_on_simple(services))
    report.findings.extend(check_image_tags(services, lines))
    report.findings.extend(check_orphan_volumes(data))
    report.findings.extend(check_env_files(services, path))
    return report


def render_text(report: Report, errors_only: bool = False) -> str:
    out: list[str] = []
    out.append(f"docker-compose-doctor — repo: {Path.cwd()}")
    out.append(f"  archivo: {Path(report.file).name} ({report.services_count} servicios)")
    out.append("")
    if not report.findings:
        out.append("✓ Sin hallazgos. OK para `docker compose up`.")
        return "\n".join(out)
    if report.errors:
        out.append("[errors]")
        for f in report.errors:
            line = f"  ✗ {f.message}"
            out.append(line)
            if f.suggestion:
                out.append(f"    Sugerencia: {f.suggestion}")
        out.append("")
    if report.warnings and not errors_only:
        out.append("[warnings]")
        for f in report.warnings:
            out.append(f"  ⚠ {f.message}")
            if f.suggestion:
                out.append(f"    Sugerencia:\n        {f.suggestion}")
        out.append("")
    out.append(f"Resumen: {len(report.errors)} errores, {len(report.warnings)} warnings.")
    return "\n".join(out)


def render_json(reports: list[Report]) -> str:
    return json.dumps(
        [
            {
                "file": r.file,
                "services_count": r.services_count,
                "errors": [asdict(f) for f in r.errors],
                "warnings": [asdict(f) for f in r.warnings],
            }
            for r in reports
        ],
        indent=2,
        ensure_ascii=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docker-compose-doctor",
        description="Análisis estático de archivos compose.yml.",
    )
    parser.add_argument("path", nargs="?", help="Ruta al compose.yml. Si se omite, busca en cwd.")
    parser.add_argument("--errors-only", action="store_true", help="Omite warnings en el output.")
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra cada check ejecutado.")
    args = parser.parse_args(argv)

    if args.path:
        target = Path(args.path)
        if not target.exists():
            sys.stderr.write(f"ERROR: {target} no existe.\n")
            return 2
        files = [target]
    else:
        files = find_compose_files(Path.cwd())

    if not files:
        sys.stderr.write("No se encontró ningún compose.yml en cwd (hasta 3 niveles).\n")
        return 2

    reports = [diagnose(f) for f in files]

    if args.json:
        print(render_json(reports))
    else:
        for r in reports:
            print(render_text(r, errors_only=args.errors_only))
            print()

    has_error = any(r.errors for r in reports)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
