"""Orchestrates modular checks into a GateReport."""

from __future__ import annotations

import json
from pathlib import Path

from release_gate.adapters.bitbucket import BitbucketAdapter
from release_gate.adapters.dpm import DpmAdapter
from release_gate.adapters.jira import JiraAdapter
from release_gate.adapters.sast import SastAdapter
from release_gate.adapters.sonar import SonarAdapter
from release_gate.checks import CHECK_RUNNERS
from release_gate.checks.context import CheckContext
from release_gate.config import Settings, load_catalog
from release_gate.models import GateInput, GateReport, ManualOverride
from release_gate.rules import checks_for_phase


class ReleaseGateEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.catalog = load_catalog(settings.catalog_path)
        self.jira = JiraAdapter(settings.jira, dry_run=settings.dry_run)
        self.bitbucket = BitbucketAdapter(settings.bitbucket, dry_run=settings.dry_run)
        self.sonar = SonarAdapter(settings.sonar, dry_run=settings.dry_run)
        self.dpm = DpmAdapter(settings.dpm, dry_run=settings.dry_run)
        self.sast = SastAdapter(settings.sast, dry_run=settings.dry_run)

    def close(self) -> None:
        for adapter in (self.jira, self.bitbucket, self.sonar, self.dpm, self.sast):
            adapter.close()

    def run(
        self,
        gate_input: GateInput,
        *,
        overrides: list[ManualOverride] | None = None,
    ) -> GateReport:
        # Mode from settings is the default; CLI may override via gate_input.mode
        ctx = CheckContext(
            settings=self.settings,
            catalog=self.catalog,
            gate_input=gate_input,
            jira=self.jira,
            bitbucket=self.bitbucket,
            sonar=self.sonar,
            dpm=self.dpm,
            sast=self.sast,
        )
        report = GateReport(
            release_id=gate_input.release_id,
            repository=gate_input.repository,
            commit=gate_input.commit,
            pr_id=gate_input.pr_id,
            phase=gate_input.phase,
            mode=gate_input.mode,
            overrides=list(overrides or []),
        )
        for check_id in checks_for_phase(gate_input.phase):
            runner = CHECK_RUNNERS.get(check_id)
            if not runner:
                continue
            report.checks.append(runner(ctx))
        report.recompute_overall()
        return report


def load_overrides(path: Path | None) -> list[ManualOverride]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("overrides") or []
    return [ManualOverride.model_validate(item) for item in data]
