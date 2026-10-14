from __future__ import annotations

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def check_sast_dependencies(ctx: CheckContext) -> CheckResult:
    check_id = "sast_dependencies"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []

    # Allow injecting findings via extra for offline / CI artifact mode
    injected = (ctx.gate_input.extra or {}).get("sast_findings")
    findings: list[dict] = []

    if injected is not None:
        findings = list(injected)
    elif not ctx.sast.configured:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="SAST adapter is not configured",
            evidence=evidence,
            policy=policy,
        )
    else:
        try:
            payload = ctx.sast.get_findings(ctx.gate_input.repository, ctx.gate_input.commit)
            findings = list(payload.get("findings") or [])
        except AdapterError as exc:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.UNKNOWN,
                summary=f"SAST unavailable: {exc}",
                evidence=evidence,
                policy=policy,
            )

    high = [f for f in findings if str(f.get("severity", "")).upper() in {"HIGH", "CRITICAL", "HI"}]
    medium = [f for f in findings if str(f.get("severity", "")).upper() in {"MEDIUM", "MED"}]

    evidence.append(Evidence(label="findings_total", value=str(len(findings))))
    evidence.append(Evidence(label="high", value=str(len(high))))
    evidence.append(Evidence(label="medium", value=str(len(medium))))
    for f in high[:5]:
        evidence.append(
            Evidence(
                label="finding",
                value=f"{f.get('severity')}: {f.get('title') or f.get('id')}",
            )
        )

    if high:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary=f"{len(high)} high/critical finding(s) - track as tech debt if deferred",
            evidence=evidence,
            policy=policy,
            details={"high": high, "medium": medium},
        )
    if medium:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary=f"{len(medium)} medium finding(s) observed",
            evidence=evidence,
            policy=policy,
            details={"high": high, "medium": medium},
        )
    return CheckResult(
        check_id=check_id,
        title=title,
        status=CheckStatus.PASS,
        summary="No SAST/dependency findings reported",
        evidence=evidence,
        policy=policy,
    )
