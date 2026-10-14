"""Normalized contracts for inputs, catalog and check results."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


class Phase(str, Enum):
    PR = "pr"
    RELEASE = "release"


class GateMode(str, Enum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


class SeverityPolicy(str, Enum):
    """How a rule behaves in enforce mode."""

    BLOCK = "block"
    WARN = "warn"
    OBSERVE = "observe"


class EscalationContact(BaseModel):
    role: str
    name: str | None = None
    email: str | None = None


class ServiceRecord(BaseModel):
    service_id: str
    name: str
    cluster: str | None = None
    impact: str | None = None
    pio: str | None = None
    delivery: str | None = None
    repository: str | None = None
    project_key: str | None = None
    kae_ids: list[str] = Field(default_factory=list)
    escalation: list[EscalationContact] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KaeRecord(BaseModel):
    kae_id: str
    name: str
    platforms: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    """Versioned source of truth: repository → service → KAE → owners."""

    version: str = "1"
    generated_at: datetime | None = None
    source: str | None = None
    services: list[ServiceRecord] = Field(default_factory=list)
    kaes: list[KaeRecord] = Field(default_factory=list)

    def service_by_repo(self, repository: str) -> ServiceRecord | None:
        repo = repository.lower().rstrip("/")
        for svc in self.services:
            if svc.repository and svc.repository.lower().rstrip("/") == repo:
                return svc
        return None

    def service_by_id(self, service_id: str) -> ServiceRecord | None:
        for svc in self.services:
            if svc.service_id == service_id:
                return svc
        return None

    def kae_by_id(self, kae_id: str) -> KaeRecord | None:
        for kae in self.kaes:
            if kae.kae_id == kae_id:
                return kae
        return None


class GateInput(BaseModel):
    release_id: str
    repository: str
    commit: str
    pr_id: int | None = None
    phase: Phase = Phase.PR
    mode: GateMode = GateMode.SHADOW
    project: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    label: str
    value: str
    url: str | None = None


class CheckResult(BaseModel):
    check_id: str
    title: str
    status: CheckStatus
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    policy: SeverityPolicy = SeverityPolicy.WARN
    details: dict[str, Any] = Field(default_factory=dict)


class ManualOverride(BaseModel):
    check_id: str
    reason: str
    approver: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GateReport(BaseModel):
    release_id: str
    repository: str
    commit: str
    pr_id: int | None = None
    phase: Phase
    mode: GateMode
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checks: list[CheckResult] = Field(default_factory=list)
    overrides: list[ManualOverride] = Field(default_factory=list)
    overall: CheckStatus = CheckStatus.UNKNOWN

    def recompute_overall(self) -> CheckStatus:
        overridden = {o.check_id for o in self.overrides}
        ranks = {
            CheckStatus.PASS: 0,
            CheckStatus.WARN: 1,
            CheckStatus.UNKNOWN: 2,
            CheckStatus.BLOCK: 3,
        }
        worst = CheckStatus.PASS
        for check in self.checks:
            if check.check_id in overridden:
                continue
            status = check.status
            # Soften statuses that are observe-only, or all blocks while in shadow for exit/overall display
            if status == CheckStatus.BLOCK and check.policy == SeverityPolicy.OBSERVE:
                status = CheckStatus.WARN
            elif status == CheckStatus.BLOCK and check.policy == SeverityPolicy.WARN:
                status = CheckStatus.WARN
            elif (
                status == CheckStatus.BLOCK
                and self.mode == GateMode.SHADOW
                and check.policy == SeverityPolicy.BLOCK
            ):
                # Keep visibility as WARN at overall level; individual check stays BLOCK in report
                status = CheckStatus.WARN
            if ranks[status] > ranks[worst]:
                worst = status
        self.overall = worst
        return self.overall

    def exit_code(self) -> int:
        """Non-zero only when enforce mode has unresolved BLOCK."""
        if self.mode == GateMode.SHADOW:
            return 0
        overridden = {o.check_id for o in self.overrides}
        has_block = any(
            c.status == CheckStatus.BLOCK
            and c.check_id not in overridden
            and c.policy == SeverityPolicy.BLOCK
            for c in self.checks
        )
        if has_block:
            return 2
        if self.overall == CheckStatus.UNKNOWN:
            return 3
        return 0
