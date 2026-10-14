from __future__ import annotations

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def check_approvals(ctx: CheckContext) -> CheckResult:
    check_id = "approvals"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []

    if ctx.gate_input.pr_id is None:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="No PR id - cannot evaluate reviewers",
            evidence=evidence,
            policy=policy,
        )

    if not ctx.bitbucket.configured:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="Bitbucket is not configured",
            evidence=evidence,
            policy=policy,
        )

    try:
        reviewers = ctx.bitbucket.get_reviewers(ctx.gate_input.repository, ctx.gate_input.pr_id)
        approved = [r for r in reviewers if r.get("approved")]
        evidence.append(Evidence(label="reviewers", value=str(len(reviewers))))
        evidence.append(Evidence(label="approved", value=str(len(approved))))
        for r in approved[:10]:
            user = (r.get("user") or {}).get("displayName") or (r.get("user") or {}).get("name")
            evidence.append(Evidence(label="approver", value=str(user)))

        if approved:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.PASS,
                summary=f"{len(approved)} approval(s) present",
                evidence=evidence,
                policy=policy,
            )
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary="No approvals yet",
            evidence=evidence,
            policy=policy,
        )
    except AdapterError as exc:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary=f"Bitbucket unavailable: {exc}",
            evidence=evidence,
            policy=policy,
        )
