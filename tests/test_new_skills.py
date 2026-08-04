"""
Tests funcionales de los skills incorporados en v0.3.0: python-lint-guard,
python-deps-pinning, version-bump (version_probe) y md-to-doc.

Cubren la lógica de decisión de cada uno — la parte donde una regla mal
aplicada produce daño real: clasificar un badge como historia, contar como
auditable una dependencia que el scanner no puede resolver, o auto-corregir
una violación que oculta un bug.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def load(skill: str, module: str, relpath: str | None = None):
    """Importa un script de skill. Los nombres de carpeta llevan guiones, así
    que no se pueden importar por ruta de paquete."""
    path = SKILLS / skill / (relpath or f"{module}.py")
    name = f"_skill_{module}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"no se pudo cargar {path}"
    mod = importlib.util.module_from_spec(spec)
    # Debe estar en sys.modules ANTES de ejecutarlo: los scripts usan
    # `from __future__ import annotations` + @dataclass, y dataclasses resuelve
    # las anotaciones diferidas mirando sys.modules[cls.__module__].
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


plg = load("python-lint-guard", "python_lint_guard")
pdp = load("python-deps-pinning", "python_deps_pinning")
vpb = load("version-bump", "version_probe")
mtd = load("md-to-doc", "md_to_doc")


class TestPythonLintGuardParity(unittest.TestCase):
    def _report(self, declared: dict, ci: dict, *, hook=True, files=("a.py",)):
        rep = plg.Report(root=REPO)
        rep.files = list(files)
        rep.declared = declared
        rep.ci_tools = ci
        rep.hook_installed = hook
        plg.check_parity(rep)
        return {f.code for f in rep.findings}

    def test_declared_but_not_in_ci_is_error(self):
        codes = self._report({"ruff": "pyproject.toml"}, {})
        self.assertIn("PARITY-NO-CI", codes)

    def test_ci_without_config_is_warning_not_error(self):
        rep = plg.Report(root=REPO)
        rep.files = ["a.py"]
        rep.ci_tools = {"ruff": "ci.yml"}
        rep.hook_installed = True
        plg.check_parity(rep)
        finding = next(f for f in rep.findings if f.code == "PARITY-NO-CONFIG")
        self.assertEqual(finding.level, "warn")

    def test_two_formatters_conflict(self):
        codes = self._report(
            {"black": "pyproject.toml", "ruff": "pyproject.toml"},
            {"black": "ci.yml", "ruff": "ci.yml"},
        )
        self.assertIn("PARITY-CONFLICT", codes)

    def test_single_formatter_is_not_a_conflict(self):
        codes = self._report({"black": "pyproject.toml"}, {"black": "ci.yml"})
        self.assertNotIn("PARITY-CONFLICT", codes)

    def test_no_gate_at_all_is_reported(self):
        codes = self._report({}, {})
        self.assertIn("PARITY-NO-GATE", codes)

    def test_mechanical_and_judgment_sets_are_disjoint(self):
        """Una regla no puede ser a la vez auto-corregible y de criterio."""
        self.assertFalse(plg.MECHANICAL & set(plg.JUDGMENT))

    def test_dangerous_rules_are_never_mechanical(self):
        """F841 borra variables: auto-corregirla puede ocultar un bug real."""
        for rule in ("F841", "E402", "S110", "C901"):
            self.assertNotIn(rule, plg.MECHANICAL, f"{rule} no debe auto-corregirse")


class TestDepsPinningClassification(unittest.TestCase):
    def test_exact_pin_is_auditable(self):
        self.assertEqual(pdp.classify_spec("==2.31.0", False), pdp.EXACT)

    def test_range_without_lock_is_not_auditable(self):
        self.assertEqual(pdp.classify_spec(">=2.0", False), pdp.RANGE)
        self.assertNotIn(pdp.RANGE, pdp.AUDITABLE)

    def test_range_with_lock_is_auditable(self):
        self.assertEqual(pdp.classify_spec(">=2.0", True), pdp.LOCKED)
        self.assertIn(pdp.LOCKED, pdp.AUDITABLE)

    def test_bare_dependency_is_not_auditable(self):
        self.assertEqual(pdp.classify_spec("", False), pdp.BARE)

    def test_wildcard_pin_is_not_exact(self):
        """`==1.2.*` no fija una versión concreta: no es un pin."""
        self.assertNotEqual(pdp.classify_spec("==1.2.*", False), pdp.EXACT)

    def test_environment_marker_does_not_break_classification(self):
        self.assertEqual(pdp.classify_spec('==2.31.0 ; python_version<"3.12"', False), pdp.EXACT)

    def test_coverage_of_unpinned_file_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("flask\nnumpy>=1.0\n", encoding="utf-8")
            rep = pdp.scan(root)
            self.assertEqual(rep.total, 2)
            self.assertEqual(rep.auditable, 0)
            self.assertEqual(rep.coverage, 0.0)

    def test_coverage_of_pinned_file_is_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("flask==3.0.0\nnumpy==2.1.0\n", encoding="utf-8")
            rep = pdp.scan(root)
            self.assertEqual(rep.coverage, 100.0)
            self.assertEqual(rep.invisible, [])

    def test_comments_and_flags_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text(
                "# comentario\n--index-url https://example.invalid\n-r otro.txt\nflask==3.0.0\n",
                encoding="utf-8",
            )
            rep = pdp.scan(root)
            self.assertEqual(rep.total, 1)


class TestVersionProbeClassification(unittest.TestCase):
    def _kind(self, filename: str, line: str, in_unreleased: bool = False) -> str:
        root = Path("/repo")
        return vpb.classify(root / filename, root, 1, line, in_unreleased)[0]

    def test_badge_is_current_even_when_linking_to_changelog(self):
        """El caso que rompe el bump: un badge que enlaza al CHANGELOG sigue
        siendo estado actual, no historia."""
        line = "[![Version](https://img.shields.io/badge/version-0.2.0-1f6feb)](CHANGELOG.md)"
        self.assertEqual(self._kind("ROADMAP.md", line), vpb.CURRENT)

    def test_changelog_entry_is_historic(self):
        self.assertEqual(self._kind("CHANGELOG.md", "## [0.2.0] — 2026-07-01"), vpb.HISTORIC)

    def test_changelog_unreleased_section_is_current(self):
        self.assertEqual(
            self._kind("CHANGELOG.md", "- algo de 0.3.0", in_unreleased=True), vpb.CURRENT
        )

    def test_manifest_version_field_is_current(self):
        self.assertEqual(self._kind("package.json", '  "version": "0.2.0",'), vpb.CURRENT)

    def test_past_tense_is_historic(self):
        self.assertEqual(
            self._kind("README.md", "**v0.2.0 · publicada 2026-07-01** — release inicial"),
            vpb.HISTORIC,
        )

    def test_unclear_line_is_ambiguous_not_guessed(self):
        """El probe no adivina: lo que no tiene señal se marca para revisión."""
        self.assertEqual(self._kind("NOTAS.md", "ver 0.2.0 para detalles"), vpb.AMBIGUOUS)

    def test_scan_finds_canonical_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text('{"version": "1.4.2"}', encoding="utf-8")
            self.assertEqual(vpb.find_canonical(root), [("package.json", "1.4.2")])


class TestMdToDoc(unittest.TestCase):
    def _ctx(self, **kw):
        return mtd.Ctx(root=REPO, **kw)

    def test_heading_and_paragraph(self):
        html, headings = mtd.md_to_html("# Título\n\nUn párrafo.\n", REPO, self._ctx())
        self.assertIn("<h1", html)
        self.assertIn("<p>Un párrafo.</p>", html)
        self.assertEqual(headings[0][1], "Título")

    def test_code_fence_is_escaped(self):
        html, _ = mtd.md_to_html("```python\nprint('<script>')\n```\n", REPO, self._ctx())
        self.assertIn('<pre class="code">', html)
        self.assertNotIn("<script>", html)

    def test_mermaid_without_layer_stays_as_text(self):
        html, _ = mtd.md_to_html("```mermaid\nflowchart LR\n  A-->B\n```\n", REPO, self._ctx())
        self.assertIn('class="mermaid"', html)

    def test_table_is_rendered(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        html, _ = mtd.md_to_html(md, REPO, self._ctx())
        self.assertIn("<table>", html)
        self.assertIn("<th>a</th>", html)

    def test_missing_image_is_reported_not_silently_dropped(self):
        ctx = self._ctx()
        html, _ = mtd.md_to_html("![alt](no-existe.png)\n", REPO, ctx)
        self.assertIn("imagen no encontrada", html)
        self.assertTrue(any("no-existe.png" in n for n in ctx.notes))

    def test_local_image_is_embedded_as_data_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # PNG 1x1 mínimo válido.
            png = bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                "1f15c4890000000a49444154789c6300010000050001"
                "0d0a2db40000000049454e44ae426082"
            )
            (base / "p.png").write_bytes(png)
            html, _ = mtd.md_to_html("![x](p.png)\n", base, self._ctx())
            self.assertIn("data:image/png;base64,", html)

    def test_exec_layer_is_off_by_default(self):
        """Ejecutar código del Markdown nunca debe ocurrir sin pedirlo."""
        ctx = self._ctx()
        self.assertIsNone(mtd.exec_block("print('x')", "python", ctx))

    def test_numeric_prefix_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            for name in ("10-diez.md", "02-dos.md", "01-uno.md"):
                (src / name).write_text("# x", encoding="utf-8")
            names = [p.name for p in mtd.discover(src, None)]
            self.assertEqual(names, ["01-uno.md", "02-dos.md", "10-diez.md"])


if __name__ == "__main__":
    unittest.main()
