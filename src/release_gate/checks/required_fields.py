from __future__ import annotations

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def check_required_fields(ctx: CheckContext) -> CheckResult:
    check_id = "required_fields"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []

    if not ctx.jira.configured:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="Jira is not configured",
            evidence=evidence,
            policy=policy,
        )

    try:
        issue = ctx.release_issue()
        if not issue:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.UNKNOWN,
                summary="Release issue not loaded",
                policy=policy,
            )

        missing: list[str] = []
        contour = issue.get("contour")
        # Contour may also be represented as a label prefix
        labels = [str(x).lower() for x in (issue.get("labels") or [])]
        has_contour_label = any(lbl.startswith("contour:") or lbl.startswith("контур:") for lbl in labels)
        if not _present(contour) and not has_contour_label:
            missing.append("contour")
        evidence.append(
            Evidence(
                label="contour",
                value=str(contour) if contour else ("label" if has_contour_label else "missing"),
            )
        )

        br = issue.get("business_requirements")
        if not _present(br):
            missing.append("business_requirements")
        evidence.append(
            Evidence(label="business_requirements", value="present" if _present(br) else "missing")
        )

        if missing:
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.BLOCK,
                summary=f"Missing required fields: {', '.join(missing)}",
                evidence=evidence,
                policy=policy,
                details={"missing": missing},
            )
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.PASS,
            summary="Required Jira fields present",
            evidence=evidence,
            policy=policy,
        )
    except AdapterError as exc:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary=f"Jira unavailable: {exc}",
            evidence=evidence,
            policy=policy,
        )
