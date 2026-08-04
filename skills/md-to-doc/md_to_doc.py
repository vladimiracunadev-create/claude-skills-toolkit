#!/usr/bin/env python3
"""
md-to-doc — renderiza un árbol de Markdown a un documento HTML autocontenido
(y opcionalmente PDF), con las imágenes embebidas.

El núcleo funciona con Python stdlib y nada más: descubre los `.md`, los ordena,
los convierte a HTML y **embebe cada imagen como data URI**, de modo que el
resultado es un único fichero que se puede abrir, mover o adjuntar sin
arrastrar carpetas de assets.

Todo lo demás son capas opt-in que degradan con aviso si falta la herramienta:

    --layer images     Pillow    reescala y optimiza; convierte a gris en perfil print
    --layer highlight  pygments  resaltado de sintaxis en los bloques de código
    --layer diagrams   mmdc      renderiza fences ```mermaid a PNG (caché por hash)
    --layer exec       —         ejecuta bloques marcados y captura su salida real
    --layer pdf        xhtml2pdf convierte el HTML resultante a PDF

Uso:
    python md_to_doc.py                                   # cwd -> DOCUMENT.html
    python md_to_doc.py --src docs --out manual.html
    python md_to_doc.py --layer diagrams --layer highlight
    python md_to_doc.py --profile print --layer images --layer pdf --out manual.pdf

Trabaja sobre Path.cwd(). Agnóstico del contenido: sirve para docs/, ADRs,
runbooks, notas o cualquier colección de Markdown.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as html_mod
import io
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        pass

_VENDOR = {
    "node_modules", "target", "dist", "build", "site-packages",
    "__pycache__", ".venv", "venv", "vendor",
}
LAYERS = ("images", "highlight", "diagrams", "exec", "pdf")

# Fence que el usuario marca explícitamente para ejecutar: ```python run
EXEC_TAG = re.compile(r"^(?P<lang>[a-zA-Z0-9_+-]*)\s+run\b")


@dataclass
class Ctx:
    root: Path
    profile: str = "color"
    layers: set[str] = field(default_factory=set)
    cache: Path | None = None
    notes: list[str] = field(default_factory=list)
    exec_timeout: int = 10

    def note(self, msg: str) -> None:
        if msg not in self.notes:
            self.notes.append(msg)


# ------------------------------------------------------------ descubrimiento

def _skip(p: Path, base: Path) -> bool:
    """True si la ruta cae en vendor o en un directorio oculto. `base` es el
    directorio de origen del barrido — no el cwd: `--src` puede apuntar fuera."""
    try:
        parts = p.relative_to(base).parts[:-1]
    except ValueError:
        return True
    return any(part in _VENDOR or (part.startswith(".") and part != ".") for part in parts)


def _sort_key(p: Path, root: Path) -> tuple:
    """Ordena por prefijo numérico cuando existe (01-, 02-…), luego alfabético.
    Es la convención más común para documentación secuencial."""
    rel_parts = p.relative_to(root).parts
    key: list = []
    for part in rel_parts:
        m = re.match(r"^(\d+)[-_. ]", part)
        key.append((0, int(m.group(1)), part.lower()) if m else (1, 0, part.lower()))
    return tuple(key)


def discover(src: Path, explicit_order: Path | None) -> list[Path]:
    """Devuelve los .md en orden. Si hay SUMMARY.md o un fichero de orden, manda."""
    if explicit_order and explicit_order.is_file():
        out = []
        for line in explicit_order.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                cand = (src / line).resolve()
                if cand.is_file():
                    out.append(cand)
        if out:
            return out

    summary = src / "SUMMARY.md"
    if summary.is_file():
        out = []
        for m in re.finditer(r"\]\(([^)]+\.md)\)", summary.read_text(encoding="utf-8")):
            cand = (src / m.group(1)).resolve()
            if cand.is_file() and cand not in out:
                out.append(cand)
        if out:
            return out

    files = [p for p in src.rglob("*.md") if not _skip(p, src) and p.name != "SUMMARY.md"]
    return sorted(files, key=lambda p: _sort_key(p, src))


# ------------------------------------------------------------------ imágenes

def data_uri(path: Path, ctx: Ctx) -> str | None:
    """Convierte una imagen a data URI. Con la capa `images`, la optimiza antes."""
    if not path.is_file():
        return None
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"

    if "images" in ctx.layers:
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            ctx.note("capa `images` pedida pero Pillow no está instalado — imágenes sin optimizar (pip install pillow)")
        else:
            try:
                with Image.open(io.BytesIO(raw)) as im:
                    if im.mode in ("RGBA", "LA", "P"):
                        bg = Image.new("RGB", im.size, (255, 255, 255))
                        im = im.convert("RGBA")
                        bg.paste(im, mask=im.split()[-1])
                        im = bg
                    else:
                        im = im.convert("RGB")
                    if ctx.profile == "print":
                        im = im.convert("L")
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=85, optimize=True)
                    raw, mime = buf.getvalue(), "image/jpeg"
            except Exception:
                ctx.note(f"no se pudo optimizar {path.name} — se embebe el original")

    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


# ------------------------------------------------------------------ mermaid

def render_mermaid(source: str, ctx: Ctx) -> str | None:
    """Renderiza un diagrama mermaid a PNG con mmdc, cacheando por hash del
    contenido: un diagrama que no cambió no se vuelve a renderizar."""
    if "diagrams" not in ctx.layers:
        return None
    mmdc = shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if not mmdc:
        ctx.note("capa `diagrams` pedida pero `mmdc` no está en PATH — los mermaid quedan como texto (npm i -g @mermaid-js/mermaid-cli)")
        return None

    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    cache_dir = ctx.cache or (Path(tempfile.gettempdir()) / "md-to-doc-cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    png = cache_dir / f"{digest}.png"

    if not png.is_file():
        src_file = cache_dir / f"{digest}.mmd"
        src_file.write_text(source, encoding="utf-8")
        try:
            proc = subprocess.run(
                [mmdc, "-i", str(src_file), "-o", str(png), "-b", "transparent"],
                capture_output=True, text=True, timeout=120, check=False,
            )
            if proc.returncode != 0 or not png.is_file():
                ctx.note(f"mmdc falló en un diagrama ({proc.returncode}) — queda como texto")
                return None
        except (OSError, subprocess.TimeoutExpired):
            ctx.note("mmdc no pudo ejecutarse — los mermaid quedan como texto")
            return None

    return data_uri(png, ctx)


# -------------------------------------------------------------- ejecución

def exec_block(code: str, lang: str, ctx: Ctx) -> str | None:
    """Ejecuta un bloque marcado con ```<lang> run y captura su salida real.

    Solo se activa con --layer exec. Ejecuta código del propio Markdown: úsalo
    únicamente sobre fuentes en las que confías."""
    if "exec" not in ctx.layers:
        return None
    interp = {"python": sys.executable, "py": sys.executable}.get(lang.lower())
    if not interp:
        ctx.note(f"bloque `{lang} run` ignorado — solo se ejecuta Python")
        return None
    try:
        proc = subprocess.run(
            [interp, "-I", "-"], input=code, capture_output=True, text=True,
            timeout=ctx.exec_timeout, check=False, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return "[md-to-doc] la ejecución excedió el tiempo límite"
    return (proc.stdout or "") + (proc.stderr or "")


# ------------------------------------------------------ resaltado de sintaxis

def highlight_code(code: str, lang: str, ctx: Ctx) -> str:
    if "highlight" in ctx.layers:
        try:
            from pygments import highlight  # type: ignore
            from pygments.formatters import HtmlFormatter  # type: ignore
            from pygments.lexers import TextLexer, get_lexer_by_name  # type: ignore
        except ImportError:
            ctx.note("capa `highlight` pedida pero pygments no está instalado — código sin resaltar (pip install pygments)")
        else:
            try:
                lexer = get_lexer_by_name(lang) if lang else TextLexer()
            except Exception:
                lexer = TextLexer()
            return highlight(code, lexer, HtmlFormatter(nowrap=True))
    return html_mod.escape(code)


# ------------------------------------------------------------ markdown → html

_INLINE = [
    (re.compile(r"`([^`]+)`"), lambda m: f"<code>{html_mod.escape(m.group(1))}</code>"),
    (re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), None),   # imágenes: se tratan aparte
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
     lambda m: f'<a href="{html_mod.escape(m.group(2), quote=True)}">{m.group(1)}</a>'),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: f"<strong>{m.group(1)}</strong>"),
    (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), lambda m: f"<em>{m.group(1)}</em>"),
    (re.compile(r"~~([^~]+)~~"), lambda m: f"<del>{m.group(1)}</del>"),
]


def inline(text: str, base: Path, ctx: Ctx) -> str:
    """Convierte el markdown inline de una línea. Las imágenes se resuelven
    relativas al fichero que las declara y se embeben como data URI."""
    placeholders: dict[str, str] = {}

    def stash(fragment: str) -> str:
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = fragment
        return key

    def img_sub(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2).split(" ")[0].strip("<>")
        if re.match(r"^[a-z]+://", src) or src.startswith("data:"):
            return stash(f'<img src="{html_mod.escape(src, quote=True)}" alt="{html_mod.escape(alt)}">')
        uri = data_uri((base / src).resolve(), ctx)
        if uri is None:
            ctx.note(f"imagen no encontrada: {src} (desde {base.name})")
            return stash(f'<span class="missing">[imagen no encontrada: {html_mod.escape(src)}]</span>')
        return stash(f'<img src="{uri}" alt="{html_mod.escape(alt)}">')

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img_sub, text)
    text = html_mod.escape(text)

    for pattern, repl in _INLINE:
        if repl is None:
            continue
        text = pattern.sub(repl, text)

    for key, fragment in placeholders.items():
        text = text.replace(html_mod.escape(key), fragment).replace(key, fragment)
    return text


def md_to_html(text: str, base: Path, ctx: Ctx) -> tuple[str, list[tuple[int, str, str]]]:
    """Convierte un documento Markdown a HTML. Devuelve (html, headings)."""
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    i, n = 0, len(lines)
    list_stack: list[str] = []

    def close_lists() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < n:
        line = lines[i]

        # --- bloque de código / mermaid ------------------------------------
        fence = re.match(r"^\s*```+\s*(.*)$", line)
        if fence:
            close_lists()
            info = fence.group(1).strip()
            body: list[str] = []
            i += 1
            while i < n and not re.match(r"^\s*```+\s*$", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(body)

            if info.lower().startswith("mermaid"):
                uri = render_mermaid(code, ctx)
                if uri:
                    out.append(f'<figure class="diagram"><img src="{uri}" alt="diagrama"></figure>')
                else:
                    out.append(f'<pre class="mermaid">{html_mod.escape(code)}</pre>')
                continue

            m_exec = EXEC_TAG.match(info)
            lang = (m_exec.group("lang") if m_exec else info.split()[0] if info else "")
            out.append(f'<pre class="code"><code>{highlight_code(code, lang, ctx)}</code></pre>')
            if m_exec:
                captured = exec_block(code, lang, ctx)
                if captured is not None and captured.strip():
                    out.append(f'<pre class="console">{html_mod.escape(captured.rstrip())}</pre>')
            continue

        # --- encabezado -----------------------------------------------------
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            close_lists()
            level, raw = len(h.group(1)), h.group(2).strip()
            anchor = "h-" + hashlib.sha1(f"{base}:{raw}".encode()).hexdigest()[:10]
            headings.append((level, raw, anchor))
            out.append(f'<h{level} id="{anchor}">{inline(raw, base, ctx)}</h{level}>')
            i += 1
            continue

        # --- regla horizontal ----------------------------------------------
        if re.match(r"^\s*([-*_])\s*(\1\s*){2,}$", line):
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        # --- tabla ----------------------------------------------------------
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            close_lists()
            def cells(row: str) -> list[str]:
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            out.append("<table><thead><tr>")
            out.extend(f"<th>{inline(c, base, ctx)}</th>" for c in head)
            out.append("</tr></thead><tbody>")
            while i < n and "|" in lines[i] and lines[i].strip():
                out.append("<tr>")
                out.extend(f"<td>{inline(c, base, ctx)}</td>" for c in cells(lines[i]))
                out.append("</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        # --- cita ------------------------------------------------------------
        if line.lstrip().startswith(">"):
            close_lists()
            quote: list[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            inner = " ".join(q for q in quote if q.strip())
            out.append(f"<blockquote>{inline(inner, base, ctx)}</blockquote>")
            continue

        # --- listas -----------------------------------------------------------
        li = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if li:
            tag = "ul" if li.group(2) in "-*+" else "ol"
            if not list_stack:
                list_stack.append(tag)
                out.append(f"<{tag}>")
            elif list_stack[-1] != tag:
                out.append(f"</{list_stack.pop()}>")
                list_stack.append(tag)
                out.append(f"<{tag}>")
            out.append(f"<li>{inline(li.group(3), base, ctx)}</li>")
            i += 1
            continue

        # --- párrafo / línea en blanco ----------------------------------------
        if not line.strip():
            close_lists()
            i += 1
            continue

        close_lists()
        para: list[str] = []
        while i < n and lines[i].strip() and not re.match(r"^\s*(```|#{1,6}\s|>|\s*([-*+]|\d+[.)])\s)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(para), base, ctx)}</p>")

    close_lists()
    return "\n".join(out), headings


# ------------------------------------------------------------------- plantilla

def build_css(profile: str) -> str:
    if profile == "print":
        accent, muted, code_bg, border = "#000", "#444", "#f2f2f2", "#999"
    else:
        accent, muted, code_bg, border = "#1f6feb", "#57606a", "#f6f8fa", "#d0d7de"
    return f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 0 2rem 4rem; font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
        line-height: 1.65; color: #111; max-width: 62rem; margin-inline: auto; }}
h1, h2, h3, h4, h5, h6 {{ line-height: 1.25; margin-top: 2em; color: {accent}; }}
h1 {{ font-size: 2rem; border-bottom: 2px solid {border}; padding-bottom: .3em; }}
h2 {{ font-size: 1.5rem; border-bottom: 1px solid {border}; padding-bottom: .25em; }}
a {{ color: {accent}; }}
code {{ background: {code_bg}; padding: .15em .35em; border-radius: 4px;
        font-family: "Cascadia Code", Consolas, monospace; font-size: .9em; }}
pre.code {{ background: {code_bg}; border: 1px solid {border}; border-radius: 8px;
            padding: 1rem; overflow-x: auto; page-break-inside: avoid; }}
pre.code code {{ background: none; padding: 0; }}
pre.console {{ background: #111; color: #eee; border-radius: 8px; padding: 1rem;
               overflow-x: auto; font-size: .85em; page-break-inside: avoid; }}
pre.mermaid {{ background: {code_bg}; border: 1px dashed {border}; border-radius: 8px;
               padding: 1rem; overflow-x: auto; }}
blockquote {{ border-left: 4px solid {border}; margin: 1em 0; padding: .1em 1em; color: {muted}; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid {border}; padding: .5em .7em; text-align: left; }}
th {{ background: {code_bg}; }}
img {{ max-width: 100%; height: auto; }}
figure.diagram {{ margin: 1.5em 0; text-align: center; page-break-inside: avoid; }}
hr {{ border: none; border-top: 1px solid {border}; margin: 2.5em 0; }}
.missing {{ color: #b00; font-style: italic; }}
.cover {{ text-align: center; padding: 6rem 0 3rem; }}
.cover h1 {{ border: none; font-size: 2.6rem; margin-bottom: .2em; }}
.cover .sub {{ color: {muted}; font-size: 1.15rem; }}
.toc {{ margin: 2rem 0 3rem; }}
.toc a {{ text-decoration: none; }}
.toc .lvl-2 {{ padding-left: 1.2rem; }}
.toc .lvl-3 {{ padding-left: 2.4rem; font-size: .93em; }}
.doc {{ page-break-before: always; }}
.notes {{ margin-top: 3rem; padding: 1rem; border: 1px dashed {border}; color: {muted}; font-size: .9em; }}
@media print {{ body {{ max-width: none; padding: 0; }} a {{ color: inherit; text-decoration: none; }} }}
"""


def build_document(title: str, subtitle: str, parts: list[tuple[str, str, list]], ctx: Ctx) -> str:
    toc: list[str] = ['<nav class="toc"><h2>Índice</h2>']
    for _, _, headings in parts:
        for level, raw, anchor in headings:
            if level <= 3:
                toc.append(f'<div class="lvl-{level}"><a href="#{anchor}">{html_mod.escape(raw)}</a></div>')
    toc.append("</nav>")

    body = "\n".join(f'<section class="doc">{html}</section>' for _, html, _ in parts)

    notes = ""
    if ctx.notes:
        items = "".join(f"<li>{html_mod.escape(nt)}</li>" for nt in ctx.notes)
        notes = f'<div class="notes"><strong>Avisos de generación</strong><ul>{items}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_mod.escape(title)}</title>
<style>{build_css(ctx.profile)}</style>
</head>
<body>
<header class="cover">
  <h1>{html_mod.escape(title)}</h1>
  {f'<p class="sub">{html_mod.escape(subtitle)}</p>' if subtitle else ''}
</header>
{''.join(toc)}
{body}
{notes}
</body>
</html>
"""


def to_pdf(html: str, out: Path, ctx: Ctx) -> bool:
    try:
        from xhtml2pdf import pisa  # type: ignore
    except ImportError:
        ctx.note("capa `pdf` pedida pero xhtml2pdf no está instalado — se generó solo HTML (pip install xhtml2pdf)")
        return False
    try:
        with out.open("wb") as fh:
            result = pisa.CreatePDF(io.StringIO(html), dest=fh, encoding="utf-8")
        return not result.err
    except Exception as exc:  # pragma: no cover
        ctx.note(f"xhtml2pdf falló: {exc}")
        return False


# ------------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="md-to-doc",
        description="Renderiza un árbol de Markdown a un documento HTML autocontenido (y opcionalmente PDF).",
    )
    ap.add_argument("--src", default=".", help="Directorio con los .md (por defecto: cwd).")
    ap.add_argument("--out", default=None, help="Fichero de salida (.html o .pdf).")
    ap.add_argument("--title", default=None, help="Título del documento.")
    ap.add_argument("--subtitle", default="", help="Subtítulo del documento.")
    ap.add_argument("--profile", choices=("color", "print"), default="color",
                    help="`print` usa paleta monocroma y convierte las imágenes a gris.")
    ap.add_argument("--layer", action="append", choices=LAYERS, default=[],
                    help="Capa opcional. Repetible. Degrada con aviso si falta la herramienta.")
    ap.add_argument("--order", default=None, help="Fichero con el orden explícito de los .md, uno por línea.")
    ap.add_argument("--cache", default=None, help="Directorio de caché para los diagramas renderizados.")
    ap.add_argument("--exec-timeout", type=int, default=10, help="Segundos máximos por bloque ejecutado.")
    args = ap.parse_args(argv)

    root = Path.cwd()
    src = (root / args.src).resolve()
    if not src.is_dir():
        sys.stderr.write(f"ERROR: {src} no es un directorio.\n")
        return 2

    ctx = Ctx(
        root=root,
        profile=args.profile,
        layers=set(args.layer),
        cache=Path(args.cache).resolve() if args.cache else None,
        exec_timeout=args.exec_timeout,
    )

    if "exec" in ctx.layers:
        sys.stderr.write(
            "⚠  Capa `exec` activa: se ejecutará el código de los bloques marcados\n"
            "   ```<lang> run del Markdown de origen. Úsala solo con fuentes de confianza.\n"
        )

    files = discover(src, Path(args.order).resolve() if args.order else None)
    if not files:
        sys.stderr.write(f"ERROR: no se encontró ningún .md bajo {src}.\n")
        return 2

    parts: list[tuple[str, str, list]] = []
    for md in files:
        text = md.read_text(encoding="utf-8", errors="replace")
        html, headings = md_to_html(text, md.parent, ctx)
        parts.append((str(md), html, headings))

    title = args.title or src.name or root.name
    document = build_document(title, args.subtitle, parts, ctx)

    out_arg = args.out or ("DOCUMENT.pdf" if "pdf" in ctx.layers else "DOCUMENT.html")
    out = (root / out_arg).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    wrote_pdf = False
    if out.suffix.lower() == ".pdf" or "pdf" in ctx.layers:
        pdf_path = out if out.suffix.lower() == ".pdf" else out.with_suffix(".pdf")
        wrote_pdf = to_pdf(document, pdf_path, ctx)
        if wrote_pdf:
            print(f"✓ PDF generado: {pdf_path}")
        else:
            out = out.with_suffix(".html")

    if not wrote_pdf:
        out.write_text(document, encoding="utf-8")
        print(f"✓ HTML autocontenido generado: {out}")

    print(f"  documentos procesados: {len(files)}")
    print(f"  perfil: {ctx.profile} · capas: {', '.join(sorted(ctx.layers)) or 'ninguna (solo núcleo stdlib)'}")
    for note in ctx.notes:
        print(f"  ⚠ {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
