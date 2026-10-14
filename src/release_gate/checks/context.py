"""Shared runtime context for checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from release_gate.adapters.bitbucket import BitbucketAdapter
from release_gate.adapters.dpm import DpmAdapter
from release_gate.adapters.jira import JiraAdapter
from release_gate.adapters.sast import SastAdapter
from release_gate.adapters.sonar import SonarAdapter
from release_gate.config import Settings
from release_gate.models import Catalog, GateInput


@dataclass
class CheckContext:
    settings: Settings
    catalog: Catalog
    gate_input: GateInput
    jira: JiraAdapter
    bitbucket: BitbucketAdapter
    sonar: SonarAdapter
    dpm: DpmAdapter
    sast: SastAdapter
    cache: dict[str, Any] = field(default_factory=dict)

    def release_issue(self) -> dict[str, Any] | None:
        if "release_issue" in self.cache:
            return self.cache["release_issue"]
        if not self.jira.configured:
            self.cache["release_issue"] = None
            return None
        data = self.jira.get_release_composition(self.gate_input.release_id)
        self.cache["release_issue"] = data
        return data

    def changed_files(self) -> list[str]:
        if self.gate_input.changed_files:
            return list(self.gate_input.changed_files)
        if "changed_files" in self.cache:
            return self.cache["changed_files"]
        files: list[str] = []
        if (
            self.gate_input.pr_id is not None
            and self.bitbucket.configured
        ):
            files = self.bitbucket.list_pr_changed_files(
                self.gate_input.repository,
                self.gate_input.pr_id,
            )
        self.cache["changed_files"] = files
        return files
