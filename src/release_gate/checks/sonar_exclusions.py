from __future__ import annotations

import fnmatch

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def _is_legal(path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in prefixes:
        if "**" in pattern or "*" in pattern:
            if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(
                normalized, pattern.replace("**/", "")
            ):
                return True
            # also try matching any path segment
            if fnmatch.fnmatch(normalized, "*/" + pattern.lstrip("*/")):
                return True
        else:
            if normalized.startswith(pattern) or f"/{pattern}" in f"/{normalized}":
                return True
    return False


def _matches_exclusion(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        p = pattern.strip()
        if not p:
            continue
        if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(normalized, p.lstrip("/")):
            return True
        # Sonar often uses **/foo/**
        if fnmatch.fnmatch(normalized, p.replace("**/", "*")):
            return True
    return False


def check_sonar_exclusions(ctx: CheckContext) -> CheckResult:
    check_id = "sonar_exclusions"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []

    files = ctx.changed_files()
    evidence.append(Evidence(label="changed_files_count", value=str(len(files))))

    if not ctx.sonar.configured:
        # Offline demo: treat empty exclusions as PASS with observation note
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="SonarQube is not configured - cannot evaluate exclusions",
            evidence=evidence,
            policy=policy,
        )

    component = (ctx.gate_input.extra or {}).get("sonar_component") or ctx.gate_input.repository.replace(
        "/", ":"
    )
    try:
        exclusions = ctx.sonar.get_exclusions(component)
        evidence.append(Evidence(label="exclusion_patterns", value=",".join(exclusions) or "(none)"))
    except AdapterError as exc:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary=f"SonarQube unavailable: {exc}",
            evidence=evidence,
            policy=policy,
        )

    red: list[str] = []
    yellow: list[str] = []
    for path in files:
        if _matches_exclusion(path, exclusions):
            if _is_legal(path, ctx.settings.legal_exclusion_prefixes):
                yellow.append(path)
            else:
                red.append(path)

    evidence.append(Evidence(label="red_zone", value=",".join(red) or "(none)"))
    evidence.append(Evidence(label="yellow_zone", value=",".join(yellow) or "(none)"))

    if red:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.BLOCK if policy.value == "block" else CheckStatus.WARN,
            summary=f"Red zone: {len(red)} changed file(s) covered by Sonar exclusions",
            evidence=evidence,
            policy=policy,
            details={"red": red, "yellow": yellow},
        )
    if yellow:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary=f"Yellow zone: {len(yellow)} legal exclusion(s) (tests/mocks)",
            evidence=evidence,
            policy=policy,
            details={"red": red, "yellow": yellow},
        )
    return CheckResult(
        check_id=check_id,
        title=title,
        status=CheckStatus.PASS,
        summary="No changed files hit Sonar exclusion list",
        evidence=evidence,
        policy=policy,
        details={"red": red, "yellow": yellow},
    )
