"""
Tests funcionales de `bitcoin-custody-audit`.

Cubren la lógica de decisión — la parte donde una regla mal aplicada produce
daño real en una custodia: dar por «no afectado» un cruce que en realidad es
indecidible, contar una etapa omitida como aprobada, o dejar pasar un quorum
N-de-N donde perder un dispositivo es perder los fondos.

Se ejecutan con `python -m unittest discover -s tests`.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def load(skill: str, module: str):
    path = SKILLS / skill / f"{module}.py"
    name = f"_skill_{module}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"no se pudo cargar {path}"
    mod = importlib.util.module_from_spec(spec)
    # En sys.modules ANTES de exec_module: el script combina
    # `from __future__ import annotations` con @dataclass.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bca = load("bitcoin-custody-audit", "bitcoin_custody_audit")


def _audit(inventory: dict | None = None, root: Path | None = None,
           today: date = date(2026, 8, 20)) -> "bca.Audit":
    return bca.Audit(root=root or REPO, today=today, inventory=inventory,
                     inventory_path=None if inventory is None else REPO / "custody.json",
                     inventory_error="" if inventory else "sin inventario")


class TestFirmwareMatching(unittest.TestCase):
    def test_below_range_is_affected(self):
        self.assertIs(bca.firmware_affected("3.9.0", "<4.1.0"), True)

    def test_above_range_is_not_affected(self):
        self.assertIs(bca.firmware_affected("5.1.2", "<4.1.0"), False)

    def test_compound_range(self):
        self.assertIs(bca.firmware_affected("1.3.0", ">=1.2 <1.5"), True)
        self.assertIs(bca.firmware_affected("1.6.0", ">=1.2 <1.5"), False)

    def test_all_means_every_version(self):
        self.assertIs(bca.firmware_affected("9.9.9", "all"), True)

    def test_unknown_firmware_is_undecidable_not_safe(self):
        """El fallo que este skill existe para evitar: resolver la ignorancia
        como «no afectado»."""
        self.assertIsNone(bca.firmware_affected("unknown", "<4.1.0"))
        self.assertIsNone(bca.firmware_affected("", "<4.1.0"))

    def test_unparseable_spec_is_undecidable(self):
        self.assertIsNone(bca.firmware_affected("1.0.0", "las builds de otoño"))


class TestInventoryPrimitives(unittest.TestCase):
    def test_quorum_forms(self):
        for raw in ("2-de-3", "2 de 3", "2 of 3", "2/3", {"m": 2, "n": 3}):
            with self.subTest(raw=raw):
                self.assertEqual(bca.parse_quorum(raw), (2, 3))

    def test_quorum_n_of_n(self):
        self.assertEqual(bca.parse_quorum("3-de-3"), (3, 3))

    def test_unknown_is_not_a_declared_value(self):
        for raw in ("unknown", "desconocido", "n/a", "", None, "  "):
            with self.subTest(raw=raw):
                self.assertFalse(bca._declared(raw))
        self.assertTrue(bca._declared("5.1.2"))


class TestStageSemantics(unittest.TestCase):
    def test_skipped_stage_is_never_counted_as_executed(self):
        audit = _audit()
        audit.stages = [bca.stage_01_provenance(audit)]
        self.assertEqual(audit.stages[0].status, bca.SKIP)
        self.assertEqual(audit.executed, [])
        self.assertEqual(len(audit.skipped), 1)

    def test_fail_wins_over_warn(self):
        stage = bca.Stage(1, "t", "A")
        stage.add("W-X", "deuda")
        stage.add("F-Y", "rotura")
        stage.resolve("ok")
        self.assertEqual(stage.status, bca.FAIL)

    def test_only_warnings_do_not_fail(self):
        stage = bca.Stage(1, "t", "A")
        stage.add("W-X", "deuda")
        stage.resolve("ok")
        self.assertEqual(stage.status, bca.WARN)


class TestStage01Provenance(unittest.TestCase):
    def _codes(self, inventory: dict) -> set[str]:
        audit = _audit(inventory)
        return {f.code for f in bca.stage_01_provenance(audit).findings}

    def test_missing_firmware_is_a_finding(self):
        codes = self._codes({"signers": [
            {"id": "a", "vendor": "coldcard", "model": "Mk4",
             "firmware_at_seed": "unknown", "entropy_source": "device"}]})
        self.assertIn("F-PROV-INCOMPLETA", codes)

    def test_signer_inside_advisory_fails(self):
        codes = self._codes({
            "signers": [{"id": "a", "vendor": "coldcard", "model": "Mk3",
                         "firmware_at_seed": "3.9.0", "entropy_source": "device"}],
            "advisories": [{"id": "CC-1", "vendor": "coldcard", "models": ["Mk3"],
                            "firmware_affected": "<4.1.0"}],
        })
        self.assertIn("F-PROV-AVISO", codes)

    def test_signer_outside_advisory_is_clean(self):
        codes = self._codes({
            "signers": [{"id": "a", "vendor": "coldcard", "model": "Mk3",
                         "firmware_at_seed": "5.1.2", "entropy_source": "device"}],
            "advisories": [{"id": "CC-1", "vendor": "coldcard", "models": ["Mk3"],
                            "firmware_affected": "<4.1.0"}],
        })
        self.assertEqual(codes, set())

    def test_undecidable_cross_is_reported_not_silenced(self):
        codes = self._codes({
            "signers": [{"id": "a", "vendor": "coldcard", "model": "Mk3",
                         "firmware_at_seed": "unknown", "entropy_source": "device"}],
            "advisories": [{"id": "CC-1", "vendor": "coldcard", "models": ["Mk3"],
                            "firmware_affected": "<4.1.0"}],
        })
        self.assertIn("W-PROV-INDECIDIBLE", codes)


class TestStage02Freshness(unittest.TestCase):
    def _codes(self, inventory: dict) -> set[str]:
        audit = _audit(inventory)
        return {f.code for f in bca.stage_02_advisory_freshness(audit).findings}

    def test_matrix_without_review_date_fails(self):
        self.assertIn("F-ADV-SIN-FECHA", self._codes({"advisories": []}))

    def test_matrix_older_than_180_days_fails(self):
        codes = self._codes({"advisories_reviewed": "2026-01-05", "advisories": [{"id": "x"}]})
        self.assertIn("F-ADV-RANCIA", codes)

    def test_matrix_between_90_and_180_days_warns(self):
        codes = self._codes({"advisories_reviewed": "2026-05-01", "advisories": [{"id": "x"}]})
        self.assertIn("W-ADV-VIEJA", codes)
        self.assertNotIn("F-ADV-RANCIA", codes)

    def test_vendor_in_use_without_advisories_is_flagged(self):
        codes = self._codes({
            "advisories_reviewed": "2026-08-15",
            "signers": [{"id": "a", "vendor": "ledger"}],
            "advisories": [{"id": "x", "vendor": "coldcard"}],
        })
        self.assertIn("W-ADV-FABRICANTE-SIN-COBERTURA", codes)


class TestStage03Architecture(unittest.TestCase):
    def _codes(self, inventory: dict) -> set[str]:
        audit = _audit(inventory)
        return {f.code for f in bca.stage_03_architecture(audit).findings}

    def test_singlesig_on_high_value_fails(self):
        codes = self._codes({"wallets": [
            {"id": "w", "policy": "singlesig", "value_tier": "high"}]})
        self.assertIn("F-ARQ-SINGLESIG-ALTO", codes)

    def test_n_of_n_quorum_fails(self):
        codes = self._codes({"wallets": [{"id": "w", "quorum": "3-de-3"}]})
        self.assertIn("F-ARQ-N-DE-N", codes)

    def test_single_vendor_quorum_warns(self):
        codes = self._codes({
            "wallets": [{"id": "w", "quorum": "2-de-3", "signers": ["a", "b", "c"]}],
            "signers": [{"id": s, "vendor": "coldcard"} for s in ("a", "b", "c")],
        })
        self.assertIn("W-ARQ-MONOCULTIVO", codes)

    def test_healthy_diverse_quorum_is_clean(self):
        codes = self._codes({
            "wallets": [{"id": "w", "quorum": "2-de-3", "signers": ["a", "b", "c"]}],
            "signers": [{"id": "a", "vendor": "coldcard"},
                        {"id": "b", "vendor": "trezor"},
                        {"id": "c", "vendor": "ledger"}],
        })
        self.assertEqual(codes, set())


class TestRepoStages(unittest.TestCase):
    def test_unpinned_action_fails_and_missing_permissions_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf = root / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "ci.yml").write_text(
                "on: [push]\njobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n",
                encoding="utf-8")
            codes = {f.code for f in bca.stage_12_ci_automation(_audit(root=root)).findings}
        self.assertIn("F-CI-SIN-PIN", codes)
        self.assertIn("W-CI-SIN-PERMISOS", codes)

    def test_weak_data_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("ROOTCAUSE_DATA_KEY=clave123\n", encoding="utf-8")
            codes = {f.code for f in bca.stage_11_encrypted_persistence(_audit(root=root)).findings}
        self.assertIn("F-PERS-CLAVE-DEBIL", codes)

    def test_placeholder_in_example_file_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.example").write_text("DATA_KEY=change-me\n", encoding="utf-8")
            codes = {f.code for f in bca.stage_11_encrypted_persistence(_audit(root=root)).findings}
        self.assertNotIn("F-PERS-CLAVE-DEBIL", codes)
        self.assertNotIn("W-PERS-CLAVE-EN-DISCO", codes)

    def test_open_bind_fails_but_example_only_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("HOST=0.0.0.0\n", encoding="utf-8")
            codes = {f.code for f in bca.stage_09_deployment_posture(_audit(root=root)).findings}
            self.assertIn("F-POS-BIND-ABIERTO", codes)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.example").write_text("HOST=0.0.0.0\n", encoding="utf-8")
            codes = {f.code for f in bca.stage_09_deployment_posture(_audit(root=root)).findings}
            self.assertIn("W-POS-BIND-ABIERTO", codes)

    def test_open_rpc_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bitcoin.conf").write_text(
                "rpcallowip=0.0.0.0/0\nrpcbind=0.0.0.0\nrpcpassword=hunter2\n", encoding="utf-8")
            codes = {f.code for f in bca.stage_10_node_isolation(_audit(root=root)).findings}
        self.assertIn("F-NODO-RPC-ABIERTO", codes)
        self.assertIn("F-NODO-RPC-BIND", codes)
        self.assertIn("W-NODO-CRED-ESTATICA", codes)

    def test_zero_deps_claim_contradicted_by_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Cero dependencias, de verdad.\n", encoding="utf-8")
            (root / "package.json").write_text('{"dependencies": {"left-pad": "1.0.0"}}',
                                               encoding="utf-8")
            codes = {f.code for f in bca.stage_07_dependency_surface(_audit(root=root)).findings}
        self.assertIn("F-DEP-AFIRMACION-FALSA", codes)

    def test_non_git_repo_skips_history_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = bca.stage_05_history_secrets(_audit(root=Path(tmp)))
        self.assertEqual(stage.status, bca.SKIP)


class TestRemediationPlan(unittest.TestCase):
    def test_plan_deduplicates_and_puts_failures_first(self):
        audit = _audit()
        stage = bca.Stage(1, "t", "A")
        stage.add("W-X", "deuda", "revisa esto", where="a.md")
        stage.add("F-Y", "rotura", "arregla esto", where="b.md")
        stage.add("F-Z", "otra rotura", "arregla esto", where="c.md")
        stage.resolve("ok")
        audit.stages = [stage]
        plan = bca.remediation_plan(audit)
        self.assertEqual([sev for sev, _, _ in plan], [bca.FAIL, bca.WARN])
        self.assertEqual(plan[0][1], "arregla esto")
        self.assertEqual(plan[0][2], ["b.md", "c.md"])


class TestReportHonesty(unittest.TestCase):
    def test_markdown_report_lists_what_it_did_not_check(self):
        audit = _audit()
        audit.stages = [bca.stage_01_provenance(audit)]
        report = bca.render_markdown(audit)
        self.assertIn("Etapas omitidas", report)
        self.assertIn("no** aprobadas", report)

    def test_console_declares_coverage(self):
        audit = _audit()
        audit.stages = [bca.stage_01_provenance(audit)]
        out = bca.render_console(audit)
        self.assertIn("COBERTURA", out)
        self.assertIn("OMITIDAS", out)

    def test_report_carries_no_absolute_inventory_path(self):
        audit = _audit({"signers": []})
        audit.inventory_path = REPO / "custody.json"
        self.assertEqual(audit.inventory_ref, "custody.json")


if __name__ == "__main__":
    unittest.main()
