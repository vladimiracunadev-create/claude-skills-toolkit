"""
fix-md-lint.py — Detecta, auto-corrige y reporta errores markdownlint
en archivos .md modificados antes de git push.

Errores que resuelve automaticamente:
  MD024 - Duplicate headings          (logica propia: usa contexto del padre)
  MD040 - No language in code block   (logica propia: infiere por contenido)
  MD031 - Blank lines around fences   (--fix)
  MD032 - Lists surrounded by blanks  (--fix)
  MD034 - Bare URLs                   (--fix)
  MD028 - Blank line in blockquote    (--fix)
  MD027 - Multiple spaces after >     (--fix)
  MD022 - Headings not surrounded     (--fix)
  MD026 - Trailing punctuation in h.  (--fix)
  MD029 - Ordered list item prefix    (--fix)
  MD030 - Spaces after list markers   (--fix)
  MD009 - Trailing spaces             (--fix)
  MD012 - Multiple blank lines        (--fix)
  MD047 - Single trailing newline     (--fix)

Errores que reporta pero NO toca (requieren criterio humano):
  MD025 - Multiple top-level headings (restructura implicita)
  MD014 - Dollar signs before commands (decision de estilo)
  MD042 - No empty links              (requiere URL real)
  MD051 - Link fragments              (requiere verificar ancla real)
  MD013 - Line length (desactivado en este proyecto)
  MD033 - Inline HTML (desactivado en este proyecto)
  MD041 - First line heading (desactivado en este proyecto)

Uso:
  python scripts/fix-md-lint.py              # solo archivos modificados (git)
  python scripts/fix-md-lint.py --all        # todos los .md del repo
  python scripts/fix-md-lint.py --dry-run    # reporta sin modificar
"""

import subprocess
import sys
import re
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path.cwd().resolve()

# Patrones para inferir lenguaje en bloques MD040
LANG_PATTERNS = [
    (r"^\s*(git |npm |npx |yarn |cd |ls |cp |mv |mkdir |rm |cat |echo |grep )", "bash"),
    (r"^\s*(python |pip |pip3 )", "bash"),
    (r"^\s*(aws |terraform |kubectl |docker |make )", "bash"),
    (r"^\s*\$\s", "bash"),
    (r"^\s*(pwsh|powershell|Get-|Set-|New-|Remove-)", "powershell"),
    (r"^\s*(import |from |def |class |if __name__|@pytest)", "python"),
    (r"^\s*(function\s|const |let |var |=>|module\.exports|require\()", "javascript"),
    (r"^\s*(interface |type |export |async function)", "typescript"),
    (r"^\s*(\{|\[)\s*$", "json"),
    (r'^\s*"[^"]+"\s*:', "json"),
    (r"^\s*(on:|jobs:|steps:|uses:|run:|name:|env:|with:)", "yaml"),
    (r"^\s*(<[a-zA-Z]|<!DOCTYPE|</)", "html"),
    (r"^\s*(SELECT |INSERT |UPDATE |DELETE |CREATE |ALTER )", "sql"),
    (r"^\s*(FROM |COPY |RUN |ENV |ARG |WORKDIR |EXPOSE )", "dockerfile"),
    (r"^\s*(resource |provider |variable |output |module )\s*\"", "hcl"),
    (r"^\s*(#\[|fn |use |impl |struct |enum |pub )", "rust"),
    (r"^\s*(package |import \")", "go"),
    (r"^\s*(using |namespace |public class |private |protected )", "csharp"),
    (r"^\s*(<?php|echo \$|function \$)", "php"),
    (r"^\s*(require |gem |def |class |module |attr_)", "ruby"),
    (r"^\s*(\[|\]\s*\[|\!\[)", "text"),
]


def get_modified_md_files() -> list[Path]:
    """Archivos .md modificados segun git (staged + unstaged + untracked)."""
    cmds = [
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    files = set()
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        for line in result.stdout.strip().splitlines():
            if line.endswith(".md"):
                p = ROOT / line
                if p.exists():
                    files.add(p)
    return sorted(files)


def get_all_md_files() -> list[Path]:
    """Todos los .md del repo rastreados por git."""
    result = subprocess.run(
        ["git", "ls-files", "*.md", "**/*.md"],
        capture_output=True, text=True, cwd=ROOT
    )
    return sorted(
        ROOT / line
        for line in result.stdout.strip().splitlines()
        if line.endswith(".md") and (ROOT / line).exists()
    )


def infer_language(block_lines: list[str]) -> str:
    """Infiere el lenguaje de un bloque de codigo por su contenido."""
    text = "\n".join(block_lines)
    for pattern, lang in LANG_PATTERNS:
        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            return lang
    return "text"


# ── MD040: bloques sin lenguaje ───────────────────────────────────────────────

def fix_md040(path: Path, dry_run: bool = False) -> int:
    """Agrega especificador de lenguaje a bloques de codigo sin lenguaje."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    result = []
    fixed = 0
    in_block = False
    block_lang = None
    block_lines: list[str] = []
    block_start = -1

    for line in lines:
        stripped = line.strip()
        if not in_block:
            if re.match(r"^(`{3,}|~{3,})\s*$", stripped):
                in_block = True
                block_lang = None
                block_lines = []
                block_start = len(result)
                result.append(line)
            elif re.match(r"^(`{3,}|~{3,})\S", stripped):
                in_block = True
                block_lang = "has_lang"
                result.append(line)
            else:
                result.append(line)
        else:
            if re.match(r"^(`{3,}|~{3,})\s*$", stripped):
                in_block = False
                if block_lang is None:
                    lang = infer_language(block_lines)
                    opener = result[block_start]
                    indent = opener[: len(opener) - len(opener.lstrip())]
                    fence = re.match(r"(`{3,}|~{3,})", opener.lstrip()).group(1)
                    result[block_start] = f"{indent}{fence}{lang}\n"
                    fixed += 1
                block_lang = None
                block_lines = []
                result.append(line)
            else:
                if block_lang is None:
                    block_lines.append(line.rstrip())
                result.append(line)

    if fixed > 0 and not dry_run:
        path.write_text("".join(result), encoding="utf-8")
    return fixed


# ── MD024: headings duplicados ────────────────────────────────────────────────

def _heading_level(line: str) -> int | None:
    """Retorna el nivel del heading (1-6) o None si no es heading."""
    m = re.match(r"^(#{1,6})\s+", line)
    return len(m.group(1)) if m else None


def _heading_text(line: str) -> str:
    """Extrae el texto del heading sin los #."""
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def _parent_heading(lines: list[str], current_idx: int, current_level: int) -> str:
    """Busca el heading padre mas cercano (nivel menor) antes de current_idx."""
    for i in range(current_idx - 1, -1, -1):
        lvl = _heading_level(lines[i])
        if lvl is not None and lvl < current_level:
            text = _heading_text(lines[i])
            # Acortar a 30 chars para que el heading no sea demasiado largo
            return text[:30].rstrip()
    return ""


def fix_md024(path: Path, dry_run: bool = False) -> int:
    """Resuelve headings duplicados agregando contexto del heading padre."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Detectar duplicados: (nivel, texto_normalizado) -> lista de indices
    seen: dict[tuple[int, str], list[int]] = defaultdict(list)
    for i, line in enumerate(lines):
        lvl = _heading_level(line)
        if lvl is not None:
            key = (lvl, _heading_text(line).lower())
            seen[key].append(i)

    duplicates = {key: idxs for key, idxs in seen.items() if len(idxs) > 1}
    if not duplicates:
        return 0

    fixed = 0
    result = list(lines)

    for (lvl, _), idxs in duplicates.items():
        # El primero se queda igual; los siguientes reciben sufijo de contexto
        used_texts: set[str] = {_heading_text(result[idxs[0]]).lower()}

        for position, idx in enumerate(idxs[1:], start=2):
            original = result[idx]
            parent = _parent_heading([r.rstrip("\n") for r in result], idx, lvl)
            hashes = "#" * lvl
            orig_text = _heading_text(original)

            # Construir candidato con contexto del padre
            if parent:
                candidate = f"{orig_text} \u2014 {parent}"
            else:
                candidate = f"{orig_text} ({position})"

            # Si el candidato ya existe (mismo padre que otro duplicado), agregar numero
            counter = 2
            base_candidate = candidate
            while candidate.lower() in used_texts:
                candidate = f"{base_candidate} ({counter})"
                counter += 1

            used_texts.add(candidate.lower())
            ending = "\n" if original.endswith("\n") else ""
            result[idx] = f"{hashes} {candidate}{ending}"
            fixed += 1

    if fixed > 0 and not dry_run:
        path.write_text("".join(result), encoding="utf-8")
    return fixed


# ── Markdownlint runner ───────────────────────────────────────────────────────

def run_markdownlint(files: list[Path], fix: bool = False) -> tuple[int, str]:
    """Ejecuta markdownlint-cli2 sobre los archivos dados."""
    rel_paths = [str(f.relative_to(ROOT)).replace("\\", "/") for f in files]
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    cmd = [npx, "markdownlint-cli2"] + (["--fix"] if fix else []) + rel_paths
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout + result.stderr


def parse_error_count(output: str) -> int:
    m = re.search(r"Summary:\s*(\d+)\s*error", output)
    return int(m.group(1)) if m else 0


def parse_errors(output: str) -> list[tuple[str, str, str]]:
    """Retorna lista de (archivo, linea, codigo+descripcion)."""
    errors = []
    for line in output.splitlines():
        # formato: archivo:linea codRule/name descripcion
        m = re.match(r"^(.+):(\d+)\s+(MD\d+\S+\s+.+)$", line)
        if m:
            errors.append((m.group(1), m.group(2), m.group(3)))
    return errors


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Detecta y corrige errores markdownlint antes de git push."
    )
    parser.add_argument("--all", action="store_true",
                        help="Procesar todos los .md del repo")
    parser.add_argument("--dry-run", action="store_true",
                        help="Reportar sin modificar archivos")
    args = parser.parse_args()

    files = get_all_md_files() if args.all else get_modified_md_files()
    scope = "todos los .md del repo" if args.all else "archivos .md modificados (git)"

    if not files:
        print(f"[OK] No hay archivos .md en scope ({scope}).")
        sys.exit(0)

    print(f"\n[MD-LINT-FIX] Scope: {scope}")
    print(f"  Archivos: {len(files)}")
    for f in files:
        print(f"    - {f.relative_to(ROOT)}")

    # Paso 1: escaneo inicial
    print("\n[1/4] Escaneando errores iniciales...")
    _, out_before = run_markdownlint(files, fix=False)
    errors_before = parse_error_count(out_before)

    if errors_before == 0:
        print("      Sin errores. Listo para push.")
        sys.exit(0)

    print(f"      Errores encontrados: {errors_before}")

    # Paso 2: fix MD024 (headings duplicados)
    print("\n[2/4] Corrigiendo MD024 (headings duplicados)...")
    md024_fixed = 0
    for f in files:
        n = fix_md024(f, dry_run=args.dry_run)
        if n > 0:
            print(f"      {f.relative_to(ROOT)}: {n} heading(s) renombrado(s)")
            md024_fixed += n
    if md024_fixed == 0:
        print("      Sin MD024 pendientes.")

    # Paso 3: fix MD040 (bloques sin lenguaje)
    print("\n[3/4] Corrigiendo MD040 (bloques sin lenguaje)...")
    md040_fixed = 0
    for f in files:
        n = fix_md040(f, dry_run=args.dry_run)
        if n > 0:
            print(f"      {f.relative_to(ROOT)}: {n} bloque(s) etiquetado(s)")
            md040_fixed += n
    if md040_fixed == 0:
        print("      Sin MD040 pendientes.")

    # Paso 4: auto-fix markdownlint (MD031/032/034/028/027/022/026/029/030/009/012/047)
    print("\n[4/4] Aplicando auto-fix markdownlint...")
    if not args.dry_run:
        run_markdownlint(files, fix=True)

    # Verificacion final
    _, out_after = run_markdownlint(files, fix=False)
    errors_after = parse_error_count(out_after)

    print(f"\n[RESULTADO]")
    print(f"  Errores antes  : {errors_before}")
    print(f"  MD024 fijados  : {md024_fixed}")
    print(f"  MD040 fijados  : {md040_fixed}")
    print(f"  Errores ahora  : {errors_after}")

    if errors_after == 0:
        print("  Estado         : LIMPIO - listo para git push")
        sys.exit(0)

    print("  Estado         : REQUIERE ATENCION MANUAL")
    remaining = parse_errors(out_after)
    if remaining:
        print("\n  Errores que necesitan revision humana:")
        by_rule: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for archivo, linea, desc in remaining:
            rule = re.match(r"(MD\d+)", desc)
            key = rule.group(1) if rule else "OTRO"
            by_rule[key].append((archivo, linea, desc))
        for rule, items in sorted(by_rule.items()):
            print(f"\n  [{rule}]")
            for archivo, linea, desc in items:
                print(f"    {archivo}:{linea} {desc}")
    sys.exit(1)


if __name__ == "__main__":
    main()
