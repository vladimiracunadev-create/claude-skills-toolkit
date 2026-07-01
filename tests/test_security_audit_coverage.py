"""
Tests happy-path para compute_coverage() de security-audit.

Verifica que las dependencias declaradas sin pin exacto (o manifests sin
lockfile) se reporten como FUERA del scan, y que un repo totalmente pinneado
tenga cobertura completa.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO / "skills" / "security-audit" / "security_audit.py"


def _load_security_audit():
    spec = importlib.util.spec_from_file_location("security_audit_under_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SA = _load_security_audit()


def _make_repo(tmp: str, files: dict[str, str]) -> Path:
    root = Path(tmp)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


class TestComputeCoverage(unittest.TestCase):
    def test_unpinned_requirements_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "requirements.txt": (
                    "requests==2.25.0\n"
                    "flask>=2.0\n"
                    "pandas\n"
                    "# comentario\n"
                    "-r otros.txt\n"
                ),
            })
            deps = SA.collect_dependencies(root)
            self.assertEqual(len(deps), 1, "solo requests==2.25.0 es escaneable")
            cov = SA.compute_coverage(root, deps)
            names = {u["name"] for u in cov["unpinned"]}
            self.assertEqual(names, {"flask", "pandas"})
            self.assertEqual(cov["outside_entries"], 2)
            self.assertEqual(cov["scanned_entries"], 1)

    def test_fully_pinned_repo_has_full_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "requirements.txt": "requests==2.25.0\nflask==2.3.0\n",
            })
            deps = SA.collect_dependencies(root)
            cov = SA.compute_coverage(root, deps)
            self.assertEqual(cov["unpinned"], [])
            self.assertEqual(cov["outside_entries"], 0)

    def test_package_json_without_lock_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "package.json": '{"dependencies": {"express": "^4.18.0", "lodash": "^4.17.0"}}',
            })
            cov = SA.compute_coverage(root, SA.collect_dependencies(root))
            self.assertEqual(len(cov["not_resolved"]), 1)
            self.assertEqual(cov["not_resolved"][0]["count"], 2)
            self.assertIn("package-lock.json", cov["not_resolved"][0]["reason"])

    def test_package_json_with_lock_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "package.json": '{"dependencies": {"express": "^4.18.0"}}',
                "package-lock.json": '{"packages": {}}',
            })
            cov = SA.compute_coverage(root, SA.collect_dependencies(root))
            self.assertEqual(cov["not_resolved"], [])

    def test_editable_and_url_lines_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "requirements.txt": (
                    "-e ./local-pkg\n"
                    "git+https://github.com/foo/bar.git\n"
                ),
            })
            cov = SA.compute_coverage(root, SA.collect_dependencies(root))
            self.assertEqual(cov["outside_entries"], 2)

    def test_name_canonicalization_dash_underscore(self):
        # python_dateutil (declarado) y python-dateutil (escaneado) son el mismo paquete
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {
                "requirements.txt": "python_dateutil==2.8.2\n",
            })
            deps = SA.collect_dependencies(root)
            cov = SA.compute_coverage(root, deps)
            self.assertEqual(cov["unpinned"], [],
                             "un paquete pinneado no debe reportarse como fuera del scan")

    def test_coverage_appears_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {"requirements.txt": "requests==2.25.0\nflask>=2.0\n"})
            deps = SA.collect_dependencies(root)
            cov = SA.compute_coverage(root, deps)
            report = SA.build_report(deps, {}, set(), root, [], coverage=cov)
            self.assertIn("Cobertura del scan", report)
            self.assertIn("flask", report)
            self.assertIn("FUERA del scan", report)

    def test_report_without_coverage_kwarg_unchanged(self):
        # Retrocompatibilidad: build_report sin coverage no menciona la sección
        with tempfile.TemporaryDirectory() as td:
            root = _make_repo(td, {"requirements.txt": "requests==2.25.0\n"})
            deps = SA.collect_dependencies(root)
            report = SA.build_report(deps, {}, set(), root, [])
            self.assertNotIn("Cobertura del scan", report)


if __name__ == "__main__":
    unittest.main()
