from __future__ import annotations

from pathlib import Path

from release_gate.config import Settings
from release_gate.engine import ReleaseGateEngine
from release_gate.models import CheckStatus, GateInput, GateMode, ManualOverride, Phase
from release_gate.reporting.artifacts import write_artifacts
from release_gate.reporting.render import render_pr_comment


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "catalog.yaml"


def _settings(**kwargs) -> Settings:
    base = Settings(catalog_path=CATALOG, dry_run=True, output_dir=ROOT / "artifacts-test")
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_pr_phase_shadow_for_known_service(tmp_path: Path) -> None:
    settings = _settings(output_dir=tmp_path)
    engine = ReleaseGateEngine(settings)
    try:
        report = engine.run(
            GateInput(
                release_id="REL-100",
                repository="PAY/payments-api",
                commit="abc123def456",
                pr_id=12,
                phase=Phase.PR,
                mode=GateMode.SHADOW,
                changed_files=["src/main/java/App.java", "src/test/java/AppTest.java"],
                extra={
                    "project_config": {
                        "service_id": "payments-api",
                        "kae_id": "KAE-PAY-CORE",
                        "repository": "PAY/payments-api",
                    },
                    "sast_findings": [
                        {
                            "id": "CVE-1",
                            "severity": "MEDIUM",
                            "title": "Jackson Databind",
                        }
                    ],
                },
            )
        )
    finally:
        engine.close()

    assert report.exit_code() == 0
    by_id = {c.check_id: c for c in report.checks}
    assert "service_kae_binding" in by_id
    assert by_id["service_kae_binding"].status == CheckStatus.PASS
    assert by_id["catalog_consistency"].status == CheckStatus.PASS
    # Sonar/SAST/Jira not configured → UNKNOWN or WARN from injected findings
    assert by_id["sast_dependencies"].status == CheckStatus.WARN
    assert by_id["sonar_exclusions"].status == CheckStatus.UNKNOWN

    paths = write_artifacts(report, tmp_path, marker="<!-- release-gate:report -->")
    assert paths["json"].exists()
    assert paths["html"].exists()
    comment = render_pr_comment(report, marker="<!-- release-gate:report -->")
    assert "<!-- release-gate:report -->" in comment
    assert "service_kae_binding" in comment


def test_missing_repo_blocks_kae_binding(tmp_path: Path) -> None:
    settings = _settings(output_dir=tmp_path)
    engine = ReleaseGateEngine(settings)
    try:
        report = engine.run(
            GateInput(
                release_id="REL-200",
                repository="UNKNOWN/missing",
                commit="deadbeef",
                phase=Phase.PR,
                mode=GateMode.ENFORCE,
            )
        )
    finally:
        engine.close()

    by_id = {c.check_id: c for c in report.checks}
    assert by_id["service_kae_binding"].status == CheckStatus.BLOCK
    assert report.exit_code() == 2


def test_override_clears_enforce_exit(tmp_path: Path) -> None:
    settings = _settings(output_dir=tmp_path)
    engine = ReleaseGateEngine(settings)
    try:
        report = engine.run(
            GateInput(
                release_id="REL-200",
                repository="UNKNOWN/missing",
                commit="deadbeef",
                phase=Phase.PR,
                mode=GateMode.ENFORCE,
            ),
            overrides=[
                ManualOverride(
                    check_id="service_kae_binding",
                    reason="Emergency hotfix agreed with delivery",
                    approver="s.nikonov",
                )
            ],
        )
    finally:
        engine.close()

    # Override removes the catalog BLOCK from exit scoring; UNKNOWN (unconfigured APIs) may yield exit 3
    assert report.exit_code() != 2
    assert any(o.check_id == "service_kae_binding" for o in report.overrides)


def test_release_phase_version_bump_warn(tmp_path: Path) -> None:
    settings = _settings(output_dir=tmp_path)
    engine = ReleaseGateEngine(settings)
    try:
        report = engine.run(
            GateInput(
                release_id="REL-300",
                repository="PAY/payments-api",
                commit="cafebabe",
                phase=Phase.RELEASE,
                mode=GateMode.SHADOW,
                changed_files=["README.md"],
            )
        )
    finally:
        engine.close()

    by_id = {c.check_id: c for c in report.checks}
    assert by_id["version_bump"].status == CheckStatus.WARN
