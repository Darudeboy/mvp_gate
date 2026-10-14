from __future__ import annotations

from pathlib import Path

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.checks.sonar_exclusions import check_sonar_exclusions
from release_gate.config import Settings, load_catalog
from release_gate.models import GateInput, GateMode, Phase


ROOT = Path(__file__).resolve().parents[1]


class FakeSonar:
    configured = True

    def __init__(self, patterns: list[str] | None = None, error: bool = False):
        self.patterns = patterns or []
        self.error = error

    def get_exclusions(self, component_key: str) -> list[str]:
        if self.error:
            raise AdapterError("boom", transient=True)
        return self.patterns


class Dummy:
    configured = False


def _ctx(files: list[str], sonar) -> CheckContext:
    settings = Settings(catalog_path=ROOT / "catalog" / "catalog.yaml", dry_run=True)
    return CheckContext(
        settings=settings,
        catalog=load_catalog(settings.catalog_path),
        gate_input=GateInput(
            release_id="REL-1",
            repository="PAY/payments-api",
            commit="abc",
            phase=Phase.PR,
            mode=GateMode.SHADOW,
            changed_files=files,
        ),
        jira=Dummy(),  # type: ignore[arg-type]
        bitbucket=Dummy(),  # type: ignore[arg-type]
        sonar=sonar,  # type: ignore[arg-type]
        dpm=Dummy(),  # type: ignore[arg-type]
        sast=Dummy(),  # type: ignore[arg-type]
    )


def test_red_zone_on_production_exclusion() -> None:
    result = check_sonar_exclusions(
        _ctx(
            ["src/main/java/Service.java"],
            FakeSonar(["src/main/java/**"]),
        )
    )
    assert result.status.value in {"WARN", "BLOCK"}
    assert any(path.endswith("Service.java") for path in result.details["red"])


def test_yellow_zone_for_tests() -> None:
    result = check_sonar_exclusions(
        _ctx(
            ["src/test/java/ServiceTest.java"],
            FakeSonar(["src/test/**"]),
        )
    )
    assert result.status.value == "WARN"
    assert result.details["yellow"]


def test_unknown_on_sonar_error() -> None:
    result = check_sonar_exclusions(_ctx(["a.java"], FakeSonar(error=True)))
    assert result.status.value == "UNKNOWN"
