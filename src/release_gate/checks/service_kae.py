from __future__ import annotations

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def check_service_kae_binding(ctx: CheckContext) -> CheckResult:
    check_id = "service_kae_binding"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []

    svc = ctx.catalog.service_by_repo(ctx.gate_input.repository)
    if not svc:
        evidence.append(Evidence(label="repository", value=ctx.gate_input.repository))
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.BLOCK,
            summary="Repository not found in catalog - cannot bind service to KAE",
            evidence=evidence,
            policy=policy,
        )

    evidence.append(Evidence(label="service_id", value=svc.service_id))
    evidence.append(Evidence(label="kae_ids", value=",".join(svc.kae_ids) or "(none)"))

    if not svc.kae_ids:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.BLOCK,
            summary=f"Service {svc.service_id} has no KAE binding in catalog",
            evidence=evidence,
            policy=policy,
        )

    missing_kae_defs = [k for k in svc.kae_ids if not ctx.catalog.kae_by_id(k)]
    if missing_kae_defs:
        evidence.append(Evidence(label="undefined_kaes", value=",".join(missing_kae_defs)))
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.BLOCK,
            summary=f"KAE ids referenced but not defined: {', '.join(missing_kae_defs)}",
            evidence=evidence,
            policy=policy,
        )

    # Cross-check with Jira release composition when available
    release_kaes: list[str] = []
    release_services: list[str] = []
    try:
        issue = ctx.release_issue()
        if issue:
            release_kaes = list(issue.get("kaes") or [])
            release_services = list(issue.get("services") or [])
            evidence.append(Evidence(label="release_kaes", value=",".join(release_kaes) or "(empty)"))
            evidence.append(
                Evidence(label="release_services", value=",".join(release_services) or "(empty)")
            )
    except AdapterError as exc:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary=f"Jira unavailable while checking KAE composition: {exc}",
            evidence=evidence,
            policy=policy,
        )

    # DPM autofill / block signal
    dpm_missing: list[str] = []
    dpm_blocked = False
    if ctx.dpm.configured:
        try:
            resolved = ctx.dpm.resolve_kaes(ctx.gate_input.release_id, [svc.service_id])
            dpm_kaes = list(resolved.get("kaes") or [])
            dpm_missing = list(resolved.get("missing_services") or [])
            dpm_blocked = bool(resolved.get("blocked"))
            evidence.append(Evidence(label="dpm_kaes", value=",".join(dpm_kaes) or "(empty)"))
            if dpm_missing:
                evidence.append(Evidence(label="dpm_missing_services", value=",".join(dpm_missing)))
        except AdapterError as exc:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.UNKNOWN,
                summary=f"DPM unavailable: {exc}",
                evidence=evidence,
                policy=policy,
            )

    if dpm_blocked or dpm_missing:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.BLOCK,
            summary="DPM blocks distribution registration due to missing KAEs",
            evidence=evidence,
            policy=policy,
            details={"dpm_missing": dpm_missing},
        )

    if release_services and svc.service_id not in release_services and svc.name not in release_services:
        # Service not listed in release — WARN unless KAE list is empty (then BLOCK)
        if not release_kaes:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.BLOCK,
                summary="Release composition has no KAEs and service is not listed",
                evidence=evidence,
                policy=policy,
            )
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary=f"Service {svc.service_id} not listed in release composition",
            evidence=evidence,
            policy=policy,
        )

    if release_kaes:
        overlap = set(svc.kae_ids) & set(release_kaes)
        if not overlap:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.BLOCK,
                summary="Service KAEs are not present in release KAE composition",
                evidence=evidence,
                policy=policy,
            )

    return CheckResult(
        check_id=check_id,
        title=title,
        status=CheckStatus.PASS,
        summary=f"Service {svc.service_id} bound to {', '.join(svc.kae_ids)}",
        evidence=evidence,
        policy=policy,
    )
