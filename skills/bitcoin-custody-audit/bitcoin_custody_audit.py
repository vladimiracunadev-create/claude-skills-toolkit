#!/usr/bin/env python3
"""
bitcoin-custody-audit — audita una custodia Bitcoin en 14 etapas.

`security-audit` audita EL REPOSITORIO: dependencias, CVE, SAST, secretos.
Este audita LA CUSTODIA: de dónde vienen las claves, qué las puede romper, y
si la instalación que las vigila está bien puesta. No se solapan: se encadenan.

Las tres reglas que gobiernan el skill:

  1. La cobertura se declara siempre. Un «0 hallazgos» sobre una superficie
     que no se miró es una mentira con formato de informe.
  2. Una etapa que no puede ejecutarse sale OMITIDA, nunca aprobada.
  3. La ausencia de dato es un hallazgo. No poder demostrar con qué firmware
     nació una clave ES el problema, aunque la clave esté sana.

Uso:
    python bitcoin_custody_audit.py                      # 14 etapas por consola
    python bitcoin_custody_audit.py --report             # + informe Markdown fechado
    python bitcoin_custody_audit.py --stages 1,2,3,9     # solo algunas
    python bitcoin_custody_audit.py --json
    python bitcoin_custody_audit.py --inventory custody.json
    python bitcoin_custody_audit.py --deep               # etapa 5 sobre el histórico

Trabaja sobre Path.cwd(). Solo stdlib (pyyaml opt-in para inventario YAML).
NUNCA pide, lee ni acepta material secreto: no hay una sola ruta de código que
consuma una semilla, una clave privada o una passphrase.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

try:
    import yaml  # opt-in: solo para inventarios en YAML
except ImportError:  # pragma: no cover
    yaml = None

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        pass

# ── Estados ──────────────────────────────────────────────────────────────────
OK = "OK"        # comprobado y correcto
WARN = "WARN"    # deuda: describe riesgo, no tumba el proceso
FAIL = "FAIL"    # rotura: exit 1
SKIP = "SKIP"    # no se pudo ejecutar — NUNCA se cuenta como aprobada

_GLYPH = {OK: "OK", WARN: "!!", FAIL: "XX", SKIP: ".."}

_VENDOR_DIRS = {
    "node_modules", "target", "dist", "build", "site-packages", "__pycache__",
    ".venv", "venv", ".git", "vendor", ".mypy_cache", ".pytest_cache", "coverage",
}

# Nombres de fichero que no deberían haber entrado nunca al repositorio.
FORBIDDEN_FILENAMES = re.compile(
    r"(^|/)(\.env(\.[\w-]+)?|wallet\.dat|.*\.mnemonic|seed[\w-]*\.(txt|json|md)"
    r"|.*\.(key|pem|p12|pfx)|hwi[\w-]*\.secret)$",
    re.IGNORECASE,
)
_ENV_ALLOWED = re.compile(r"\.env\.(example|sample|template|dist)$", re.IGNORECASE)

# Material secreto de dominio. xpub NO va aquí: no es secreto, es privacidad.
SECRET_PATTERNS = {
    "xprv": re.compile(r"\b[xyztuv]prv[a-km-zA-HJ-NP-Z1-9]{50,}"),
    "wif": re.compile(r"\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b"),
    "descriptor-privado": re.compile(r"\b(wpkh|wsh|sh|tr|pkh)\([^)]*[xyzt]prv"),
    "pgp-privada": re.compile(r"BEGIN (PGP|RSA|OPENSSH|EC) PRIVATE KEY"),
}
PRIVACY_PATTERNS = {
    "xpub": re.compile(r"\b[xyztuv]pub[a-km-zA-HJ-NP-Z1-9]{50,}"),
}
# Heurística de frase mnemónica: 12/15/18/21/24 tokens seguidos, minúsculas,
# 3-8 caracteres. Se reporta como HEURÍSTICA (WARN), nunca como certeza: no se
# embebe la wordlist BIP39 y por tanto no se puede confirmar.
MNEMONIC_HEURISTIC = re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b")

# Campos de API que aceptarían material secreto si nadie los frena.
SECRET_INTAKE = re.compile(
    r"\b(mnemonic|seed_?phrase|seedphrase|privkey|private_?key|xprv|wif|passphrase)\b",
    re.IGNORECASE,
)
GUARD_HINT = re.compile(
    r"\b(reject|deny|refuse|forbid|guard|block|rechaz|prohib|bloque)\w*", re.IGNORECASE
)

SOURCE_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".py", ".rs", ".go", ".java", ".cs"}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {
    ".md", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".conf", ".txt",
    ".env", ".sh", ".ps1", ".cmd", ".bat", ".html",
}


@dataclass
class Finding:
    """Un hallazgo concreto, con su acción de remediación."""
    code: str
    detail: str
    remediation: str = ""
    where: str = ""

    def as_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail,
                "remediation": self.remediation, "where": self.where}


@dataclass
class Stage:
    num: int
    title: str
    block: str
    status: str = SKIP
    coverage: str = "no evaluada"
    findings: list[Finding] = field(default_factory=list)

    def add(self, code: str, detail: str, remediation: str = "", where: str = "") -> None:
        self.findings.append(Finding(code, detail, remediation, where))

    def resolve(self, ok_msg: str) -> None:
        """Fija el estado a partir de los hallazgos. FAIL manda sobre WARN."""
        if any(f.code.startswith("F-") for f in self.findings):
            self.status = FAIL
        elif self.findings:
            self.status = WARN
        else:
            self.status = OK
            self.coverage = ok_msg or self.coverage

    def skip(self, reason: str) -> None:
        self.status = SKIP
        self.coverage = reason

    def as_dict(self) -> dict:
        return {"stage": self.num, "title": self.title, "block": self.block,
                "status": self.status, "coverage": self.coverage,
                "findings": [f.as_dict() for f in self.findings]}


@dataclass
class Audit:
    root: Path
    today: date
    inventory: dict | None = None
    inventory_path: Path | None = None
    inventory_error: str = ""
    stages: list[Stage] = field(default_factory=list)

    @property
    def inventory_ref(self) -> str:
        """Ruta del inventario relativa al repo — los informes no deben llevar
        rutas absolutas de la maquina de quien los genero."""
        if self.inventory_path is None:
            return "custody.json"
        try:
            return self.inventory_path.relative_to(self.root).as_posix()
        except ValueError:
            return str(self.inventory_path)

    @property
    def executed(self) -> list[Stage]:
        return [s for s in self.stages if s.status != SKIP]

    @property
    def skipped(self) -> list[Stage]:
        return [s for s in self.stages if s.status == SKIP]

    @property
    def failed(self) -> list[Stage]:
        return [s for s in self.stages if s.status == FAIL]


# ── Utilidades ───────────────────────────────────────────────────────────────
def _iter_files(root: Path, suffixes: set[str] | None = None, limit: int = 4000):
    """Recorre el repo saltando vendor. Devuelve rutas relativas ordenadas."""
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= limit:
            return
        if not path.is_file():
            continue
        if any(part in _VENDOR_DIRS for part in path.parts):
            continue
        if ".claude/worktrees" in path.as_posix():
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        count += 1
        yield path


def _read(path: Path, max_bytes: int = 512_000) -> str:
    try:
        with path.open("rb") as fh:
            raw = fh.read(max_bytes)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _git(root: Path, *args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _is_git_repo(root: Path) -> bool:
    code, out = _git(root, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out.strip() == "true"


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


_QUORUM = re.compile(r"(\d+)\s*(?:[-/\s]\s*)?(?:de|of)?\s*(?:[-/\s]\s*)?(\d+)", re.IGNORECASE)


def parse_quorum(value) -> tuple[int, int] | None:
    """Acepta '2-de-3', '2 of 3', '2/3' o {'m': 2, 'n': 3}."""
    if isinstance(value, dict):
        try:
            return int(value["m"]), int(value["n"])
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(value, str):
        match = _QUORUM.search(value)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


_UNKNOWN = {"", "unknown", "desconocido", "n/a", "na", "none", "null", "?", "tbd"}


def _declared(value) -> bool:
    """La ausencia de dato es un hallazgo: 'unknown' NO cuenta como declarado."""
    if value is None:
        return False
    return str(value).strip().lower() not in _UNKNOWN


# ── Inventario ───────────────────────────────────────────────────────────────
INVENTORY_CANDIDATES = [
    "custody.json", "custody.yml", "custody.yaml",
    "bitcoin-custody.json", "bitcoin-custody.yml", "bitcoin-custody.yaml",
    ".custody/inventory.json", ".custody/inventory.yml", ".custody/inventory.yaml",
    "custody/inventory.json", "custody/inventory.yml", "custody/inventory.yaml",
]


def load_inventory(root: Path, explicit: str | None = None) -> tuple[dict | None, Path | None, str]:
    """Devuelve (inventario, ruta, error). El inventario describe la custodia:
    wallets, firmantes con su PROCEDENCIA, y la matriz de avisos publicados.
    Nunca contiene material secreto — solo metadatos."""
    candidates = [Path(explicit)] if explicit else [root / c for c in INVENTORY_CANDIDATES]
    for cand in candidates:
        path = cand if cand.is_absolute() else root / cand
        if not path.is_file():
            continue
        text = _read(path)
        if path.suffix.lower() == ".json":
            try:
                return json.loads(text), path, ""
            except json.JSONDecodeError as exc:
                return None, path, f"{path.name} no es JSON válido: {exc}"
        if yaml is None:
            return None, path, (
                f"{path.name} es YAML y `pyyaml` no está instalado "
                "(pip install pyyaml, o usa un inventario .json)"
            )
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:  # pragma: no cover
            return None, path, f"{path.name} no es YAML válido: {exc}"
        if not isinstance(data, dict):
            return None, path, f"{path.name} no contiene un mapa en la raíz"
        return data, path, ""
    return None, None, "no se encontró inventario de custodia"


def _signers(inv: dict) -> list[dict]:
    return [s for s in (inv.get("signers") or []) if isinstance(s, dict)]


def _wallets(inv: dict) -> list[dict]:
    return [w for w in (inv.get("wallets") or []) if isinstance(w, dict)]


def _advisories(inv: dict) -> list[dict]:
    return [a for a in (inv.get("advisories") or []) if isinstance(a, dict)]


_VER = re.compile(r"(\d+(?:\.\d+)*)")


def _vercmp(a: str, b: str) -> int:
    """Compara versiones tipo 5.1.2. Devuelve -1, 0 o 1."""
    pa = [int(x) for x in _VER.search(a).group(1).split(".")] if _VER.search(a) else []
    pb = [int(x) for x in _VER.search(b).group(1).split(".")] if _VER.search(b) else []
    for x, y in zip(pa + [0] * len(pb), pb + [0] * len(pa)):
        if x != y:
            return -1 if x < y else 1
    return 0


_RANGE = re.compile(r"^\s*(<=|>=|<|>|==|=)?\s*v?([\d.]+)\s*$")


def firmware_affected(firmware: str, spec) -> bool | None:
    """¿La versión `firmware` cae dentro de `spec`? None = no se puede decidir.

    Acepta '<4.1.0', '>=1.2 <1.5', '==2.0', listas y 'all'/'*'."""
    if spec is None:
        return None
    if isinstance(spec, (list, tuple)):
        results = [firmware_affected(firmware, s) for s in spec]
        if any(r is True for r in results):
            return True
        return None if any(r is None for r in results) else False
    text = str(spec).strip().lower()
    if text in {"all", "*", "any", "todas"}:
        return True
    if not _declared(firmware):
        return None
    verdicts = []
    for clause in text.split():
        match = _RANGE.match(clause)
        if not match:
            return None
        op, target = match.group(1) or "==", match.group(2)
        cmp = _vercmp(firmware, target)
        verdicts.append({
            "<": cmp < 0, "<=": cmp <= 0, ">": cmp > 0,
            ">=": cmp >= 0, "==": cmp == 0, "=": cmp == 0,
        }[op])
    return all(verdicts) if verdicts else None


# ── Bloque A · Las claves ────────────────────────────────────────────────────
def stage_01_provenance(audit: Audit) -> Stage:
    """¿Se puede demostrar con qué firmware y método nació cada semilla?"""
    st = Stage(1, "Procedencia de claves y firmantes", "A · Las claves")
    inv = audit.inventory
    if inv is None:
        st.skip(f"sin inventario de custodia ({audit.inventory_error})")
        return st
    signers = _signers(inv)
    if not signers:
        st.skip("el inventario no declara firmantes (`signers`)")
        return st

    required = ("vendor", "model", "firmware_at_seed", "entropy_source")
    complete = 0
    for signer in signers:
        sid = signer.get("id") or signer.get("name") or "<sin id>"
        missing = [f for f in required if not _declared(signer.get(f))]
        if missing:
            st.add(
                "F-PROV-INCOMPLETA",
                f"firmante `{sid}`: sin declarar {', '.join(missing)}",
                "Registra la procedencia real. Si no se puede reconstruir, trata la "
                "clave como no descartable y planifica su rotación.",
                where=audit.inventory_ref,
            )
        else:
            complete += 1

    # Cruce con la matriz de avisos: aquí es donde la procedencia paga.
    advisories = _advisories(inv)
    undecidable = 0
    for signer in signers:
        sid = signer.get("id") or signer.get("name") or "<sin id>"
        vendor = str(signer.get("vendor") or "").strip().lower()
        model = str(signer.get("model") or "").strip().lower()
        firmware = str(signer.get("firmware_at_seed") or "")
        if not vendor:
            continue
        for adv in advisories:
            if str(adv.get("vendor") or "").strip().lower() != vendor:
                continue
            models = [str(m).strip().lower() for m in (adv.get("models") or [])]
            if models and model not in models:
                continue
            verdict = firmware_affected(firmware, adv.get("firmware_affected"))
            aid = adv.get("id") or adv.get("summary") or "<aviso sin id>"
            if verdict is True:
                st.add(
                    "F-PROV-AVISO",
                    f"firmante `{sid}` ({vendor} {model}, fw {firmware}) cae dentro del aviso {aid}",
                    "Rota la semilla creada con ese firmware. Detalle: "
                    + str(adv.get("url") or "sin URL declarada"),
                    where=audit.inventory_ref,
                )
            elif verdict is None:
                undecidable += 1
                st.add(
                    "W-PROV-INDECIDIBLE",
                    f"firmante `{sid}` vs aviso {aid}: no se puede decidir con los datos declarados",
                    "Completa `firmware_at_seed` del firmante o `firmware_affected` del aviso.",
                    where=audit.inventory_ref,
                )

    st.coverage = (
        f"{len(signers)} firmantes · {complete} con procedencia completa · "
        f"{len(advisories)} avisos cruzados · {undecidable} cruces indecidibles"
    )
    st.resolve(st.coverage)
    return st


def stage_02_advisory_freshness(audit: Audit) -> Stage:
    """¿La inteligencia con la que se juzga esta al dia?"""
    st = Stage(2, "Frescura de la matriz de avisos", "A · Las claves")
    inv = audit.inventory
    if inv is None:
        st.skip(f"sin inventario de custodia ({audit.inventory_error})")
        return st

    advisories = _advisories(inv)
    reviewed = _parse_date(inv.get("advisories_reviewed") or inv.get("advisories_reviewed_at"))
    if reviewed is None:
        st.add(
            "F-ADV-SIN-FECHA",
            "el inventario no declara cuándo se revisó por última vez la matriz de avisos",
            "Añade `advisories_reviewed: YYYY-MM-DD` y actualízalo en cada revisión. "
            "Un panel en verde sobre avisos sin revisar en seis meses es peor que no tenerlo.",
            where=audit.inventory_ref,
        )
        age = None
    else:
        age = (audit.today - reviewed).days
        if age > 180:
            st.add("F-ADV-RANCIA",
                   f"la matriz lleva {age} días sin revisar (límite: 180)",
                   "Revisa los avisos publicados por cada fabricante presente en el inventario.",
                   where=audit.inventory_ref)
        elif age > 90:
            st.add("W-ADV-VIEJA",
                   f"la matriz lleva {age} días sin revisar (recomendado: 90 o menos)",
                   "Programa la revisión de avisos como tarea periódica.",
                   where=audit.inventory_ref)

    vendors = {str(s.get("vendor") or "").strip().lower() for s in _signers(inv)}
    vendors.discard("")
    covered = {str(a.get("vendor") or "").strip().lower() for a in advisories}
    uncovered = sorted(vendors - covered)
    if uncovered:
        st.add("W-ADV-FABRICANTE-SIN-COBERTURA",
               "fabricantes en uso sin ningún aviso registrado: " + ", ".join(uncovered),
               "Ausencia de avisos no es ausencia de riesgo: puede significar que nadie los buscó.",
               where=audit.inventory_ref)
    if not advisories:
        st.add("W-ADV-VACIA", "la matriz de avisos esta vacía",
               "Carga al menos los avisos historicos de los fabricantes que usas.",
               where=audit.inventory_ref)

    st.coverage = (
        f"{len(advisories)} avisos · revisada hace "
        f"{age if age is not None else '?'} días · {len(vendors)} fabricantes en uso"
    )
    st.resolve(st.coverage)
    return st


def stage_03_architecture(audit: Audit) -> Stage:
    """¿La arquitectura contiene el compromiso de UN firmante?"""
    st = Stage(3, "Arquitectura de custodia", "A · Las claves")
    inv = audit.inventory
    if inv is None:
        st.skip(f"sin inventario de custodia ({audit.inventory_error})")
        return st
    wallets = _wallets(inv)
    if not wallets:
        st.skip("el inventario no declara wallets (`wallets`)")
        return st

    by_id = {s.get("id"): s for s in _signers(inv) if s.get("id")}
    high = {"high", "alto", "alta", "critical", "critico", "critica",
                "crítico", "crítica"}
    single = {"singlesig", "single-sig", "single_sig", "single", "única", "único"}
    analysed = 0
    for wallet in wallets:
        wid = wallet.get("id") or wallet.get("name") or "<sin id>"
        tier = str(wallet.get("value_tier") or wallet.get("valor") or "").strip().lower()
        quorum = parse_quorum(wallet.get("quorum"))
        policy = str(wallet.get("policy") or ("multisig" if quorum else "")).strip().lower()
        signer_ids = [s for s in (wallet.get("signers") or []) if isinstance(s, str)]
        analysed += 1

        if not quorum and policy in single:
            code = "F-ARQ-SINGLESIG-ALTO" if tier in high else "W-ARQ-SINGLESIG"
            st.add(code,
                   f"wallet `{wid}` es single-sig" + (f" con valor declarado {tier}" if tier else ""),
                   "Un solo firmante es un solo punto de fallo. Migra a multisig con "
                   "quorum m-de-n (m < n) y fabricantes distintos.",
                   where=audit.inventory_ref)
        elif quorum:
            m, n = quorum
            if m == n:
                st.add("F-ARQ-N-DE-N",
                       f"wallet `{wid}` usa quorum {m}-de-{n}: perder un firmante es perder los fondos",
                       f"Pasa a {max(1, n - 1)}-de-{n} o añade un firmante de respaldo.",
                       where=audit.inventory_ref)
            if signer_ids and len(signer_ids) != n:
                st.add("W-ARQ-QUORUM-INCOHERENTE",
                       f"wallet `{wid}` declara quorum {m}-de-{n} pero lista {len(signer_ids)} firmantes",
                       "Corrige el inventario: el análisis de diversidad depende de esa lista.",
                       where=audit.inventory_ref)
            vendors = {str(by_id.get(s, {}).get("vendor") or "").strip().lower()
                       for s in signer_ids}
            vendors.discard("")
            if signer_ids and len(vendors) == 1 and n > 1:
                st.add("W-ARQ-MONOCULTIVO",
                       f"wallet `{wid}`: los {len(signer_ids)} firmantes son del mismo fabricante "
                       f"({vendors.pop()})",
                       "Un aviso del fabricante alcanza a todo el quorum a la vez. "
                       "Diversifica al menos un firmante.",
                       where=audit.inventory_ref)
        else:
            st.add("W-ARQ-SIN-POLITICA",
                   f"wallet `{wid}` no declara `policy` ni `quorum`",
                   "Sin política declarada no se puede razonar sobre la contención.",
                   where=audit.inventory_ref)

    st.coverage = f"{analysed} wallets analizadas · {len(by_id)} firmantes referenciables"
    st.resolve(st.coverage)
    return st


# ── Bloque B · El software ───────────────────────────────────────────────────
def stage_04_secret_rejection(audit: Audit) -> Stage:
    """¿Sigue siendo imposible entregarle una semilla a la aplicacion?

    Cobertura ESTÁTICA. La versión fuerte de esta etapa se ejecuta contra la
    aplicacion en marcha; aquí se lee el código. Se declara asi en `coverage`
    para no vender como demostrado lo que solo esta leido."""
    st = Stage(4, "Rechazo de material secreto", "B · El software")
    sources = [p for p in _iter_files(audit.root, SOURCE_SUFFIXES)]
    if not sources:
        st.skip("no se encontró código fuente que analizar")
        return st

    intake: list[tuple[Path, int, str]] = []
    guarded_files = 0
    for path in sources:
        text = _read(path)
        if not text:
            continue
        has_intake = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if len(line) > 400:
                continue
            if SECRET_INTAKE.search(line):
                has_intake = True
                intake.append((path, lineno, line.strip()[:160]))
        if has_intake and GUARD_HINT.search(text):
            guarded_files += 1

    files_with_intake = {p for p, _, _ in intake}
    unguarded = []
    for path in sorted(files_with_intake):
        if not GUARD_HINT.search(_read(path)):
            unguarded.append(path)

    for path in unguarded[:20]:
        rel = path.relative_to(audit.root).as_posix()
        first = next(ln for p, ln, _ in intake if p == path)
        st.add("F-SEC-SIN-GUARDIA",
               f"`{rel}` nombra material secreto sin ninguna señal de rechazo en el fichero",
               "Toda entrada que pueda transportar una semilla debe pasar por un guardia "
               "explícito que la rechace y lo registre. Añade el guardia y un test que lo pruebe.",
               where=f"{rel}:{first}")

    if files_with_intake and not unguarded:
        st.add("W-SEC-SOLO-ESTATICO",
               f"{len(files_with_intake)} ficheros nombran material secreto y todos tienen guardia "
               "aparente, pero esto es lectura de código, no ejecución",
               "Corre la comprobacion contra la aplicacion en marcha antes de cada release.",
               where="")

    st.coverage = (
        f"{len(sources)} ficheros de código leídos · {len(files_with_intake)} nombran material "
        f"secreto · {guarded_files} con guardia aparente · análisis ESTÁTICO (no se ejecutó la app)"
    )
    st.resolve(st.coverage)
    return st


def _history_files(root: Path, deep: bool) -> list[str]:
    args = ["log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:"]
    if not deep:
        args.insert(1, "--max-count=2000")
    code, out = _git(root, *args)
    if code != 0:
        return []
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def stage_05_history_secrets(audit: Audit, deep: bool = False) -> Stage:
    """¿Entro alguna vez material secreto al repositorio?"""
    st = Stage(5, "Secretos en el histórico", "B · El software")
    if not _is_git_repo(audit.root):
        st.skip("no es un repositorio git: no hay histórico que revisar")
        return st

    ever_added = _history_files(audit.root, deep)
    for name in ever_added:
        if FORBIDDEN_FILENAMES.search(name) and not _ENV_ALLOWED.search(name):
            st.add("F-HIST-FICHERO",
                   f"`{name}` existio en el histórico (borrarlo despues no lo saca de los objetos git)",
                   "Rota TODO lo que pudo contener y purga el objeto "
                   "(git filter-repo / BFG) antes de dar el repositorio por limpio.",
                   where=name)

    scanned = 0
    for path in _iter_files(audit.root, TEXT_SUFFIXES):
        text = _read(path, max_bytes=200_000)
        if not text:
            continue
        scanned += 1
        rel = path.relative_to(audit.root).as_posix()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                st.add("F-HIST-SECRETO",
                       f"`{rel}` contiene material que parece {label}",
                       "Trata la clave como comprometida: rota primero, limpia despues.",
                       where=rel)
        for label, pattern in PRIVACY_PATTERNS.items():
            if pattern.search(text):
                st.add("W-HIST-PRIVACIDAD",
                       f"`{rel}` contiene un {label}: no es secreto, pero revela todo el historial "
                       "de la wallet a quien lo lea",
                       "Sacalo del repositorio salvo que la exposicion sea deliberada.",
                       where=rel)
        for match in MNEMONIC_HEURISTIC.finditer(text):
            words = match.group(0).split()
            if len(words) in (12, 15, 18, 21, 24):
                st.add("W-HIST-MNEMONICO-HEURISTICO",
                       f"`{rel}` contiene {len(words)} palabras seguidas con forma de frase "
                       "mnemónica (heurística: no se verifica contra la wordlist BIP39)",
                       "Revisalo a mano. Si es una semilla real, esa clave ya no es segura.",
                       where=rel)
                break

    st.coverage = (
        f"{len(ever_added)} ficheros vistos en el histórico "
        f"({'completo' if deep else 'últimos 2000 commits'}) · "
        f"{scanned} ficheros del árbol de trabajo escaneados por patron"
    )
    st.resolve(st.coverage)
    return st


def _detect_bundler(root: Path) -> tuple[str, str] | None:
    pkg = root / "package.json"
    if pkg.is_file():
        text = _read(pkg)
        for name in ("pkg", "nexe", "electron", "electron-builder"):
            if f'"{name}"' in text:
                return name, "package.json"
    for spec in root.glob("*.spec"):
        if "PyInstaller" in _read(spec) or "Analysis(" in _read(spec):
            return "pyinstaller", spec.name
    if (root / "tauri.conf.json").is_file() or (root / "src-tauri").is_dir():
        return "tauri", "tauri"
    return None


def stage_06_runtime_supply_chain(audit: Audit) -> Stage:
    """¿El motor que viaja DENTRO del binario esta identificado y fijado?"""
    st = Stage(6, "Cadena de suministro del runtime", "B · El software")
    bundler = _detect_bundler(audit.root)
    if bundler is None:
        st.skip("no se detectó empaquetado de un runtime dentro del artefacto")
        return st
    name, where = bundler

    pins: list[str] = []
    pkg = audit.root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(_read(pkg))
        except json.JSONDecodeError:
            data = {}
        engines = (data.get("engines") or {}) if isinstance(data, dict) else {}
        for key, value in engines.items():
            pins.append(f"engines.{key}={value}")
        targets = (data.get("pkg") or {}).get("targets") if isinstance(data.get("pkg"), dict) else None
        if targets:
            pins.append(f"pkg.targets={targets}")
    for candidate in (".nvmrc", ".node-version", ".python-version", "runtime.txt"):
        path = audit.root / candidate
        if path.is_file():
            pins.append(f"{candidate}={_read(path).strip()[:40]}")

    if not pins:
        st.add("F-RT-SIN-PIN",
               f"se empaqueta un runtime con `{name}` pero el repositorio no fija su versión "
               "en ningún sitio",
               "Fija la versión (engines / .nvmrc / .python-version). Sin pin no se puede "
               "saber que motor viaja dentro del binario, ni si tiene avisos abiertos.",
               where=where)

    reviewed = None
    if audit.inventory:
        reviewed = _parse_date(audit.inventory.get("runtime_advisories_reviewed"))
    reports = sorted(audit.root.glob("SECURITY_AUDIT_*.md"))
    if reviewed is None and not reports:
        st.add("W-RT-SIN-REVISION",
               "no hay constancia de haber revisado avisos del runtime empaquetado",
               "Corre `security-audit` sobre este repositorio y registra la fecha en "
               "`runtime_advisories_reviewed` del inventario. Este skill no consulta la red.",
               where=where)
    elif reviewed is not None and (audit.today - reviewed).days > 180:
        st.add("W-RT-REVISION-VIEJA",
               f"los avisos del runtime llevan {(audit.today - reviewed).days} días sin revisar",
               "Vuelve a correr `security-audit` y actualiza la fecha.",
               where=where)

    st.coverage = (
        f"empaquetador `{name}` · pins: {'; '.join(pins) if pins else 'ninguno'} · "
        "avisos del runtime NO consultados (este skill no accede a la red)"
    )
    st.resolve(st.coverage)
    return st


def stage_07_dependency_surface(audit: Audit) -> Stage:
    """¿Cuanto código de terceros se ejecuta, y se puede auditar?"""
    st = Stage(7, "Superficie de dependencias", "B · El software")
    runtime_deps: dict[str, int] = {}
    lockfiles: list[str] = []

    pkg = audit.root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(_read(pkg))
        except json.JSONDecodeError:
            data = {}
        runtime_deps["npm"] = len((data.get("dependencies") or {}) if isinstance(data, dict) else {})
        for lock in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
            if (audit.root / lock).is_file():
                lockfiles.append(lock)
    for req in sorted(audit.root.glob("requirements*.txt")):
        lines = [ln for ln in _read(req).splitlines()
                 if ln.strip() and not ln.strip().startswith(("#", "-"))]
        runtime_deps["pip"] = runtime_deps.get("pip", 0) + len(lines)
    for lock in ("poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock", "requirements.lock",
                 "Cargo.lock", "go.sum"):
        if (audit.root / lock).is_file():
            lockfiles.append(lock)
    if (audit.root / "go.mod").is_file():
        runtime_deps["go"] = len(re.findall(r"^\s+\S+\s+v\S+", _read(audit.root / "go.mod"), re.M))

    total = sum(runtime_deps.values())
    if total == 0 and not (audit.root / "package.json").is_file():
        st.skip("no se encontraron manifests de dependencias")
        return st

    # Coherencia entre lo que el repo AFIRMA y lo que declara.
    claims_zero = False
    for doc in ("README.md", "SECURITY.md"):
        path = audit.root / doc
        if path.is_file() and re.search(r"(cero|zero)[\s-]*(dependenc|deps)", _read(path), re.I):
            claims_zero = True
    if claims_zero and total > 0:
        st.add("F-DEP-AFIRMACION-FALSA",
               f"la documentación afirma cero dependencias y los manifests declaran {total}",
               "O corriges la afirmacion o eliminas las dependencias. Una promesa de seguridad "
               "que no se cumple es peor que no haberla hecho.",
               where="README.md")
    if total > 0 and not lockfiles:
        st.add("W-DEP-SIN-LOCK",
               f"{total} dependencias de runtime sin ningún lockfile",
               "Sin lockfile no hay versión exacta que consultar: ningún scanner puede "
               "pronunciarse. Genera el lockfile y corre `python-deps-pinning`.",
               where="")

    st.coverage = (
        f"{total} dependencias de runtime declaradas "
        f"({', '.join(f'{k}:{v}' for k, v in sorted(runtime_deps.items())) or 'ninguna'}) · "
        f"lockfiles: {', '.join(lockfiles) or 'ninguno'}"
    )
    st.resolve(st.coverage)
    return st


_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")


def stage_08_repo_integrity(audit: Audit) -> Stage:
    """¿El repositorio contiene lo que dice contener?"""
    st = Stage(8, "Integridad del repositorio", "B · El software")
    docs = [p for p in _iter_files(audit.root, {".md"})]
    if not docs:
        st.skip("no hay documentación Markdown que verificar")
        return st

    checked = 0
    broken = 0
    for doc in docs:
        text = _read(doc)
        for match in _MD_LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "data:", "//")):
                continue
            checked += 1
            resolved = (doc.parent / target).resolve()
            if not resolved.exists():
                broken += 1
                rel = doc.relative_to(audit.root).as_posix()
                critical = bool(_RUNBOOK.search(rel)) or doc.name in {
                    "SECURITY.md", "README.md", "INSTALL.md"}
                if broken <= 25:
                    st.add("F-INT-ENLACE-ROTO" if critical else "W-INT-ENLACE-ROTO",
                           f"`{rel}` enlaza a `{target}`, que no existe",
                           "Corrige el enlace o restaura el fichero. Un runbook que remite a un "
                           "documento inexistente falla justo cuando hace falta.",
                           where=rel)

    st.coverage = f"{len(docs)} documentos · {checked} enlaces internos resueltos · {broken} rotos"
    st.resolve(st.coverage)
    return st


# ── Bloque C · La instalación ────────────────────────────────────────────────
CONFIG_NAMES = (
    ".env", ".env.example", ".env.sample", ".env.local", "config.cmd", "config.sh",
    "config.json", "config.yml", "config.yaml", "settings.json",
    "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml",
)
_OPEN_BIND = re.compile(
    r"\b(HOST|BIND|BIND_ADDRESS|LISTEN|SERVER_HOST)\s*[:=]\s*[\"']?(0\.0\.0\.0|::|\*)",
    re.IGNORECASE,
)
_PORT_OPEN = re.compile(r"^\s*-\s*[\"']?(?:0\.0\.0\.0:)?(\d{2,5}):(\d{2,5})[\"']?\s*$", re.M)
_TRUE = re.compile(r"[:=]\s*[\"']?(true|1|yes|on)[\"']?\s*$", re.IGNORECASE)


def _config_files(root: Path) -> list[Path]:
    found = [root / name for name in CONFIG_NAMES if (root / name).is_file()]
    for sub in ("config", "deploy", "etc"):
        directory = root / sub
        if directory.is_dir():
            found.extend(p for p in sorted(directory.glob("*"))
                         if p.is_file() and p.suffix.lower() in {".env", ".json", ".yml", ".yaml", ".conf", ".ini"})
    return found


def stage_09_deployment_posture(audit: Audit) -> Stage:
    """¿Cómo está configurada la instalación AHORA MISMO?"""
    st = Stage(9, "Postura de la instalación", "C · La instalación")
    configs = _config_files(audit.root)
    if not configs:
        st.skip("no se encontraron ficheros de configuración en el repositorio")
        return st

    for path in configs:
        rel = path.relative_to(audit.root).as_posix()
        example = _ENV_ALLOWED.search(path.name) or "example" in path.name or "sample" in path.name
        text = _read(path)
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _OPEN_BIND.search(stripped):
                st.add("W-POS-BIND-ABIERTO" if example else "F-POS-BIND-ABIERTO",
                       f"`{rel}` escucha en todas las interfaces: {stripped[:100]}",
                       "Una consola de custodia se sirve en 127.0.0.1. Si necesitas verla desde "
                       "otro equipo, usa un tunel SSH, no un bind abierto.",
                       where=f"{rel}:{lineno}")
            if re.match(r"\s*(DEMO_MODE|DEBUG|DEV_MODE|INSECURE\w*)\s*[:=]", stripped, re.I) \
                    and _TRUE.search(stripped) and not example:
                st.add("W-POS-MODO-INSEGURO",
                       f"`{rel}` deja activo un modo de desarrollo: {stripped[:100]}",
                       "Con el modo demo o debug activo, lo que ves en el panel no describe "
                       "tus fondos reales.",
                       where=f"{rel}:{lineno}")
        if path.name.startswith("compose") or path.name.startswith("docker-compose"):
            for match in _PORT_OPEN.finditer(text):
                st.add("W-POS-PUERTO-PUBLICADO",
                       f"`{rel}` publica el puerto {match.group(1)} sin restringirlo a 127.0.0.1",
                       "Prefija el mapeo con `127.0.0.1:` para no exponerlo a la red local.",
                       where=rel)

    st.coverage = (
        f"{len(configs)} ficheros de configuración leídos DEL REPOSITORIO · "
        "no se inspecciono ningún proceso en ejecucion"
    )
    st.resolve(st.coverage)
    return st


NODE_CONF_NAMES = ("bitcoin.conf", "bitcoind.conf", "node.conf")
_RPC_OPEN = re.compile(r"^\s*rpcallowip\s*=\s*(0\.0\.0\.0/0|::/0|\*)", re.IGNORECASE | re.M)
_RPC_BIND = re.compile(r"^\s*rpcbind\s*=\s*(0\.0\.0\.0|::)", re.IGNORECASE | re.M)
_RPC_PASS = re.compile(r"^\s*rpcpassword\s*=\s*\S+", re.IGNORECASE | re.M)
_RPC_URL_CREDS = re.compile(r"https?://[^\s:@/]+:[^\s:@/]+@", re.IGNORECASE)


def _find_node_confs(root: Path) -> list[Path]:
    found = []
    for path in _iter_files(root, None, limit=8000):
        if path.name.lower() in NODE_CONF_NAMES:
            found.append(path)
    return found


def stage_10_node_isolation(audit: Audit) -> Stage:
    """¿El acceso al nodo es local y de solo lectura?"""
    st = Stage(10, "Aislamiento del nodo", "C · La instalación")
    confs = _find_node_confs(audit.root)
    env_hits = []
    for path in _config_files(audit.root):
        text = _read(path)
        if re.search(r"\bRPC_?(URL|USER|PASSWORD|HOST)\b", text, re.IGNORECASE):
            env_hits.append(path)
    if not confs and not env_hits:
        st.skip("no se encontró configuración de nodo Bitcoin (bitcoin.conf ni variables RPC_*)")
        return st

    for path in confs:
        rel = path.relative_to(audit.root).as_posix()
        text = _read(path)
        if _RPC_OPEN.search(text):
            st.add("F-NODO-RPC-ABIERTO",
                   f"`{rel}` acepta RPC desde cualquier origen (`rpcallowip`)",
                   "Restringe a 127.0.0.1. El RPC del nodo no es una API publica.",
                   where=rel)
        if _RPC_BIND.search(text):
            st.add("F-NODO-RPC-BIND",
                   f"`{rel}` enlaza el RPC a todas las interfaces (`rpcbind`)",
                   "Enlaza solo a 127.0.0.1.", where=rel)
        if _RPC_PASS.search(text):
            st.add("W-NODO-CRED-ESTATICA",
                   f"`{rel}` usa `rpcpassword` estatica en vez de la cookie de autenticacion",
                   "Usa `.cookie`: rota en cada arranque y no queda escrita en ningún fichero.",
                   where=rel)
        if re.search(r"^\s*disablewallet\s*=\s*0", text, re.IGNORECASE | re.M):
            st.add("W-NODO-WALLET-ACTIVA",
                   f"`{rel}` deja la wallet del nodo habilitada",
                   "Una vigilancia watch-only no necesita la wallet del nodo: "
                   "`disablewallet=1` reduce superficie.",
                   where=rel)

    for path in env_hits:
        rel = path.relative_to(audit.root).as_posix()
        text = _read(path)
        if _RPC_URL_CREDS.search(text):
            st.add("F-NODO-CRED-EN-URL",
                   f"`{rel}` embebe usuario y contraseña del RPC dentro de la URL",
                   "Saca las credenciales de la URL: acaban en logs, en el historial "
                   "del shell y en cualquier traza de error.",
                   where=rel)

    st.coverage = (
        f"{len(confs)} ficheros de nodo + {len(env_hits)} configuraciones con variables RPC "
        "revisados · no se interrogó a ningún nodo en ejecucion"
    )
    st.resolve(st.coverage)
    return st


_KEY_ASSIGN = re.compile(
    r"^\s*(?:export\s+|set\s+)?([A-Z][A-Z0-9_]*(?:DATA_KEY|_KEY|SECRET|PASSWORD|TOKEN))\s*=\s*(.*)$",
    re.MULTILINE,
)
_PLACEHOLDER = re.compile(
    r"^[\"']?(|<.*>|\.\.\.|xxx+|change[_-]?me|your[_-].*|tu[_-].*|placeholder|todo|\$\{[^}]+\}|%\w+%)[\"']?$",
    re.IGNORECASE,
)


def stage_11_encrypted_persistence(audit: Audit) -> Stage:
    """¿El estado esta cifrado y la clave es fuerte?"""
    st = Stage(11, "Persistencia cifrada", "C · La instalación")
    configs = _config_files(audit.root)
    if not configs:
        st.skip("no se encontraron ficheros de configuración donde buscar la clave de datos")
        return st

    keys_found = 0
    tracked = set()
    if _is_git_repo(audit.root):
        code, out = _git(audit.root, "ls-files")
        if code == 0:
            tracked = {line.strip() for line in out.splitlines() if line.strip()}

    for path in configs:
        rel = path.relative_to(audit.root).as_posix()
        example = _ENV_ALLOWED.search(path.name) or "example" in path.name or "sample" in path.name
        text = _read(path)
        for match in _KEY_ASSIGN.finditer(text):
            name, raw = match.group(1), match.group(2).strip().strip('"').strip("'")
            keys_found += 1
            if _PLACEHOLDER.match(raw or ""):
                continue
            lineno = text[:match.start()].count("\n") + 1
            in_git = rel in tracked
            if in_git and not example:
                st.add("F-PERS-CLAVE-VERSIONADA",
                       f"`{rel}` versiona un valor real para `{name}`",
                       "Rota la clave y saca el fichero del control de versiones. "
                       "Todo lo que estuvo en git sigue en git.",
                       where=f"{rel}:{lineno}")
            elif not example:
                st.add("W-PERS-CLAVE-EN-DISCO",
                       f"`{rel}` guarda un valor para `{name}` en texto plano",
                       "Pasa la clave por variable de entorno o gestor de secretos.",
                       where=f"{rel}:{lineno}")
            if len(raw) < 32 and not example:
                st.add("F-PERS-CLAVE-DEBIL",
                       f"`{name}` en `{rel}` mide {len(raw)} caracteres (mínimo recomendado: 32)",
                       "Genera una clave aleatoria de al menos 32 caracteres. "
                       "Una clave corta convierte el cifrado en decoracion.",
                       where=f"{rel}:{lineno}")

    if keys_found == 0:
        st.add("W-PERS-SIN-CLAVE",
               "ninguna configuración declara una clave de cifrado del estado persistido",
               "Si el estado se guarda en claro, cualquiera con acceso al disco ve el "
               "inventario completo de la custodia. Declara y usa una clave de datos.",
               where="")

    st.coverage = (
        f"{len(configs)} ficheros revisados · {keys_found} declaraciones de clave encontradas · "
        f"{len(tracked)} ficheros versionados contrastados"
    )
    st.resolve(st.coverage)
    return st


_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
_SHA = re.compile(r"@[0-9a-f]{40}$")


def stage_12_ci_automation(audit: Audit) -> Stage:
    """¿Los workflows estan pinneados y con permisos mínimos?"""
    st = Stage(12, "Automatización y CI", "C · La instalación")
    wf_dir = audit.root / ".github" / "workflows"
    workflows = sorted(p for p in wf_dir.glob("*.y*ml")) if wf_dir.is_dir() else []
    if not workflows:
        st.skip("el repositorio no tiene workflows de GitHub Actions")
        return st

    total_uses = 0
    unpinned = 0
    for path in workflows:
        rel = path.relative_to(audit.root).as_posix()
        text = _read(path)
        for match in _USES.finditer(text):
            ref = match.group(1).strip().strip('"').strip("'")
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            total_uses += 1
            if not _SHA.search(ref):
                unpinned += 1
                lineno = text[:match.start()].count("\n") + 1
                if unpinned <= 25:
                    st.add("F-CI-SIN-PIN",
                           f"`{rel}` usa `{ref}` sin fijar a SHA",
                           "Fija la accion a un SHA de 40 caracteres: una etiqueta la puede "
                           "mover quien controle el repositorio de la accion.",
                           where=f"{rel}:{lineno}")
        if not re.search(r"^\s*permissions:", text, re.MULTILINE):
            st.add("W-CI-SIN-PERMISOS",
                   f"`{rel}` no declara `permissions:`",
                   "Declara permisos mínimos explicitos (`contents: read`).",
                   where=rel)

    st.coverage = f"{len(workflows)} workflows · {total_uses} acciones · {unpinned} sin SHA"
    st.resolve(st.coverage)
    return st


_CHECKSUM_FILES = ("SHA256SUMS", "SHA256SUMS.txt", "checksums.txt", "SHASUMS256.txt")


def stage_13_artifact_verification(audit: Audit) -> Stage:
    """¿Lo publicado se puede verificar antes de ejecutarlo?"""
    st = Stage(13, "Verificación del artefacto", "C · La instalación")
    wf_dir = audit.root / ".github" / "workflows"
    release_wfs = []
    if wf_dir.is_dir():
        for path in sorted(wf_dir.glob("*.y*ml")):
            text = _read(path)
            if re.search(r"(softprops/action-gh-release|gh release create|actions/upload-artifact)", text):
                release_wfs.append(path)
    has_checksums = any((audit.root / name).is_file() for name in _CHECKSUM_FILES)
    if not release_wfs and not has_checksums:
        st.skip("no se detectó automatización de release ni ficheros de checksum")
        return st

    emits_checksum = False
    for path in release_wfs:
        text = _read(path)
        rel = path.relative_to(audit.root).as_posix()
        if re.search(r"(sha256sum|Get-FileHash|shasum\s+-a\s+256|SHA256SUMS)", text, re.IGNORECASE):
            emits_checksum = True
        else:
            st.add("F-ART-SIN-CHECKSUM",
                   f"`{rel}` publica artefactos sin generar checksums",
                   "Genera y publica SHA256 junto al binario: sin ellos nadie puede "
                   "distinguir tu artefacto de uno sustituido.",
                   where=rel)

    docs = " ".join(_read(audit.root / name) for name in ("README.md", "INSTALL.md", "SECURITY.md")
                    if (audit.root / name).is_file())
    if (emits_checksum or has_checksums) and not re.search(
            r"(sha256sum|Get-FileHash|shasum)", docs, re.IGNORECASE):
        st.add("W-ART-VERIFICACION-NO-DOCUMENTADA",
               "se publican checksums pero la documentación no explica como verificarlos",
               "Un checksum que nadie sabe comprobar no protege a nadie: documenta el comando.",
               where="README.md")
    if not re.search(r"(cosign|gpg\s+--verify|minisign|attestation)", docs, re.IGNORECASE):
        st.add("W-ART-SIN-FIRMA",
               "no hay constancia de firma criptográfica del artefacto (cosign/GPG/attestations)",
               "El checksum prueba integridad; la firma prueba origen. Para software de "
               "custodia conviene tener las dos.",
               where="")

    st.coverage = (
        f"{len(release_wfs)} workflows de release · checksums en repo: "
        f"{'sí' if has_checksums else 'no'} · el binario publicado NO se descargó ni se ejecutó"
    )
    st.resolve(st.coverage)
    return st


# ── Bloque D · Las personas ──────────────────────────────────────────────────
_RUNBOOK = re.compile(r"(runbook|incident|respuesta|response|playbook|contingenc)", re.IGNORECASE)


def stage_14_human_process(audit: Audit) -> Stage:
    """¿Existe runbook y quien decide que, ANTES de necesitarlo?"""
    st = Stage(14, "Proceso humano de respuesta", "D · Las personas")
    runbooks = [p for p in _iter_files(audit.root, {".md"}) if _RUNBOOK.search(p.name)]
    roles = {}
    if audit.inventory:
        raw = audit.inventory.get("roles")
        if isinstance(raw, dict):
            roles = {k: v for k, v in raw.items() if _declared(v)}
    security_md = audit.root / "SECURITY.md"

    if not runbooks:
        st.add("F-HUM-SIN-RUNBOOK",
               "no existe ningún documento de respuesta a incidentes",
               "Escribe el runbook ahora: durante el incidente nadie tiene tiempo de "
               "inventarse el procedimiento. Mínimo: cómo se detecta, quién se entera, "
               "qué se hace primero.",
               where="")
    if not roles:
        st.add("F-HUM-SIN-ROLES",
               "el inventario no declara quién decide qué (`roles`)",
               "Declara al menos quien aprueba mover fondos y quien custodia cada firmante. "
               "Descubrirlo durante el incidente es descubrirlo tarde.",
               where=audit.inventory_ref)
    if not security_md.is_file():
        st.add("W-HUM-SIN-SECURITY-MD",
               "no hay `SECURITY.md` con canal de contacto",
               "Publica como se reporta un problema y en cuanto tiempo se responde.",
               where="")
    elif not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://", _read(security_md)):
        st.add("W-HUM-CONTACTO-AUSENTE",
               "`SECURITY.md` no declara un canal de contacto concreto",
               "Añade un correo o un formulario: un aviso que no llega a nadie no existe.",
               where="SECURITY.md")

    st.coverage = (
        f"{len(runbooks)} documentos de respuesta · {len(roles)} roles declarados · "
        f"SECURITY.md: {'sí' if security_md.is_file() else 'no'}"
    )
    st.resolve(st.coverage)
    return st


# ── Orquestacion ─────────────────────────────────────────────────────────────
STAGE_TITLES = {
    1: "Procedencia de claves y firmantes",
    2: "Frescura de la matriz de avisos",
    3: "Arquitectura de custodia",
    4: "Rechazo de material secreto",
    5: "Secretos en el histórico",
    6: "Cadena de suministro del runtime",
    7: "Superficie de dependencias",
    8: "Integridad del repositorio",
    9: "Postura de la instalación",
    10: "Aislamiento del nodo",
    11: "Persistencia cifrada",
    12: "Automatización y CI",
    13: "Verificación del artefacto",
    14: "Proceso humano de respuesta",
}
ALL_STAGES = tuple(STAGE_TITLES)


def run_audit(root: Path, *, stages: list[int] | None = None, inventory: str | None = None,
              deep: bool = False, today: date | None = None) -> Audit:
    inv, inv_path, error = load_inventory(root, inventory)
    audit = Audit(root=root, today=today or date.today(),
                  inventory=inv, inventory_path=inv_path, inventory_error=error)
    wanted = stages or list(ALL_STAGES)
    runners = {
        1: lambda: stage_01_provenance(audit),
        2: lambda: stage_02_advisory_freshness(audit),
        3: lambda: stage_03_architecture(audit),
        4: lambda: stage_04_secret_rejection(audit),
        5: lambda: stage_05_history_secrets(audit, deep=deep),
        6: lambda: stage_06_runtime_supply_chain(audit),
        7: lambda: stage_07_dependency_surface(audit),
        8: lambda: stage_08_repo_integrity(audit),
        9: lambda: stage_09_deployment_posture(audit),
        10: lambda: stage_10_node_isolation(audit),
        11: lambda: stage_11_encrypted_persistence(audit),
        12: lambda: stage_12_ci_automation(audit),
        13: lambda: stage_13_artifact_verification(audit),
        14: lambda: stage_14_human_process(audit),
    }
    for num in wanted:
        runner = runners.get(num)
        if runner is None:
            continue
        audit.stages.append(runner())
    return audit


def remediation_plan(audit: Audit) -> list[tuple[str, str, list[str]]]:
    """Plan único y deduplicado: FAIL primero, luego WARN. Cada accion aparece
    una sola vez, con la lista de sitios donde toca aplicarla."""
    buckets: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for severity, prefix in ((FAIL, "F-"), (WARN, "W-")):
        for stage in audit.stages:
            for finding in stage.findings:
                if not finding.code.startswith(prefix):
                    continue
                key = (severity, finding.remediation or finding.detail)
                if key not in buckets:
                    buckets[key] = []
                    order.append(key)
                if finding.where and finding.where not in buckets[key]:
                    buckets[key].append(finding.where)
    return [(sev, action, buckets[(sev, action)]) for sev, action in order]


# ── Salida ───────────────────────────────────────────────────────────────────
def render_console(audit: Audit) -> str:
    lines = ["", "BITCOIN CUSTODY AUDIT", "=" * 72,
             f"Repositorio : {audit.root}",
             "Inventario  : " + (audit.inventory_ref if audit.inventory_path
                                 else "NO ENCONTRADO - " + audit.inventory_error),
             f"Fecha       : {audit.today.isoformat()}", ""]

    counts = {status: len([s for s in audit.stages if s.status == status])
              for status in (OK, WARN, FAIL, SKIP)}
    lines.append(
        f"COBERTURA   : {len(audit.executed)}/{len(audit.stages)} etapas ejecutadas · "
        f"{counts[SKIP]} OMITIDAS (no evaluadas, NO aprobadas)"
    )
    lines.append(
        f"RESULTADO   : {counts[OK]} OK · {counts[WARN]} con atención · {counts[FAIL]} fallidas"
    )
    lines.append("")

    block = ""
    for stage in audit.stages:
        if stage.block != block:
            block = stage.block
            lines.append(f"-- Bloque {block} " + "-" * max(0, 60 - len(block)))
        lines.append(f"{_GLYPH[stage.status]}  {stage.num:>2}. {stage.title}")
        lines.append(f"       cobertura: {stage.coverage}")
        for finding in stage.findings[:6]:
            lines.append(f"       - [{finding.code}] {finding.detail}")
        if len(stage.findings) > 6:
            lines.append(f"       - … y {len(stage.findings) - 6} hallazgos mas")
    lines.append("")

    plan = remediation_plan(audit)
    if plan:
        lines.append("PLAN DE REMEDIACIÓN (deduplicado, lo que rompe primero)")
        for idx, (severity, action, places) in enumerate(plan, 1):
            mark = "XX" if severity == FAIL else "!!"
            lines.append(f"  {idx:>2}. [{mark}] {action}")
            if places:
                shown = ", ".join(places[:4])
                extra = f" (+{len(places) - 4})" if len(places) > 4 else ""
                lines.append(f"       en: {shown}{extra}")
    else:
        lines.append("PLAN DE REMEDIACIÓN: sin acciones pendientes en las etapas ejecutadas.")

    if audit.skipped:
        lines.append("")
        lines.append("ETAPAS OMITIDAS — lo que este informe NO dice nada sobre:")
        for stage in audit.skipped:
            lines.append(f"  ..  {stage.num:>2}. {stage.title} — {stage.coverage}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(audit: Audit) -> str:
    counts = {status: len([s for s in audit.stages if s.status == status])
              for status in (OK, WARN, FAIL, SKIP)}
    badge = {OK: "✅", WARN: "⚠️", FAIL: "❌", SKIP: "⬜"}
    out = [
        f"# ₿ Auditoría de custodia Bitcoin — {audit.today.isoformat()}",
        "",
        f"> Generado por `bitcoin-custody-audit` sobre `{audit.root.name}`.",
        "",
        "## 📊 Resumen",
        "",
        "| | |",
        "|---|---|",
        f"| Repositorio | `{audit.root}` |",
        f"| Inventario | `{audit.inventory_ref if audit.inventory_path else 'no encontrado'}` |",
        f"| Etapas ejecutadas | **{len(audit.executed)} / {len(audit.stages)}** |",
        f"| Etapas omitidas | **{counts[SKIP]}** (no evaluadas — **no** aprobadas) |",
        f"| Resultado | {counts[OK]} OK · {counts[WARN]} con atención · {counts[FAIL]} fallidas |",
        "",
        "> [!IMPORTANT]",
        "> Una etapa omitida **no es una etapa aprobada**. Este informe solo se pronuncia",
        "> sobre las etapas que pudo ejecutar; el resto queda listado al final.",
        "",
        "## 🔍 Etapas",
        "",
        "| # | Etapa | Estado | Cobertura |",
        "|---|---|---|---|",
    ]
    for stage in audit.stages:
        out.append(f"| {stage.num} | {stage.title} | {badge[stage.status]} {stage.status} "
                   f"| {stage.coverage} |")
    out.append("")

    for stage in audit.stages:
        if not stage.findings:
            continue
        out.append(f"### {badge[stage.status]} Etapa {stage.num} — {stage.title}")
        out.append("")
        out.append("| Código | Hallazgo | Dónde |")
        out.append("|---|---|---|")
        for finding in stage.findings:
            where = f"`{finding.where}`" if finding.where else "—"
            out.append(f"| `{finding.code}` | {finding.detail} | {where} |")
        out.append("")

    out.append("## 🛠️ Plan de remediación")
    out.append("")
    plan = remediation_plan(audit)
    if plan:
        for idx, (severity, action, places) in enumerate(plan, 1):
            mark = "❌" if severity == FAIL else "⚠️"
            out.append(f"{idx}. {mark} {action}")
            if places:
                out.append(f"   - Aplica en: {', '.join(f'`{p}`' for p in places[:8])}"
                           + (f" _(+{len(places) - 8})_" if len(places) > 8 else ""))
        out.append("")
    else:
        out.append("Sin acciones pendientes en las etapas ejecutadas.")
        out.append("")

    out.append("## ⬜ Etapas omitidas")
    out.append("")
    if audit.skipped:
        out.append("| # | Etapa | Por qué no se pudo evaluar |")
        out.append("|---|---|---|")
        for stage in audit.skipped:
            out.append(f"| {stage.num} | {stage.title} | {stage.coverage} |")
    else:
        out.append("Ninguna: las 14 etapas se ejecutaron.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("### Límites de este informe")
    out.append("")
    out.append("- **No verifica la procedencia declarada.** Si el inventario registra un firmware")
    out.append("  incorrecto, el diagnóstico será incorrecto.")
    out.append("- **No consulta la red.** La matriz de avisos es la que el inventario declara.")
    out.append("- **No mira la cadena.** Sin análisis de UTXO, reutilización de direcciones ni")
    out.append("  contrapartes: es una decisión de alcance, no una carencia.")
    out.append("- **No sustituye** una auditoría criptográfica ni un proceso profesional de")
    out.append("  respuesta a incidentes.")
    out.append("")
    return "\n".join(out)


def _parse_stages(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    wanted = []
    for chunk in raw.replace(" ", "").split(","):
        if not chunk:
            continue
        if "-" in chunk:
            start, _, end = chunk.partition("-")
            try:
                wanted.extend(range(int(start), int(end) + 1))
            except ValueError:
                continue
        else:
            try:
                wanted.append(int(chunk))
            except ValueError:
                continue
    return [n for n in wanted if n in STAGE_TITLES] or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bitcoin-custody-audit",
        description="Audita una custodia Bitcoin en 14 etapas. Nunca pide material secreto.",
    )
    ap.add_argument("--inventory", metavar="PATH",
                    help="Ruta al inventario de custodia (JSON, o YAML si hay pyyaml).")
    ap.add_argument("--stages", metavar="LISTA",
                    help="Etapas a ejecutar, p.ej. `1,2,3` o `9-13`. Por defecto: las 14.")
    ap.add_argument("--deep", action="store_true",
                    help="Etapa 5 sobre el histórico completo (por defecto: últimos 2000 commits).")
    ap.add_argument("--report", action="store_true",
                    help="Escribe SECURITY_AUDIT_BITCOIN_<fecha>.md en la raíz.")
    ap.add_argument("--out-dir", metavar="DIR", help="Directorio del informe (por defecto: la raíz).")
    ap.add_argument("--json", action="store_true", help="Salida JSON procesable.")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 también si alguna etapa quedó OMITIDA.")
    args = ap.parse_args(argv)

    root = Path.cwd()
    audit = run_audit(root, stages=_parse_stages(args.stages),
                      inventory=args.inventory, deep=args.deep)

    if args.json:
        print(json.dumps({
            "root": str(audit.root),
            "date": audit.today.isoformat(),
            "inventory": audit.inventory_ref if audit.inventory_path else None,
            "inventory_error": audit.inventory_error,
            "executed": len(audit.executed),
            "skipped": len(audit.skipped),
            "failed": [s.num for s in audit.failed],
            "stages": [s.as_dict() for s in audit.stages],
            "remediation": [{"severity": sev, "action": act, "where": places}
                            for sev, act, places in remediation_plan(audit)],
        }, indent=2, ensure_ascii=False))
    else:
        print(render_console(audit))

    if args.report:
        out_dir = Path(args.out_dir).expanduser() if args.out_dir else root
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"SECURITY_AUDIT_BITCOIN_{audit.today.isoformat()}.md"
        target.write_text(render_markdown(audit), encoding="utf-8")
        try:
            shown = target.relative_to(root)
        except ValueError:
            shown = target
        print(f"Informe escrito en {shown}")

    if audit.failed:
        return 1
    if args.strict and audit.skipped:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
