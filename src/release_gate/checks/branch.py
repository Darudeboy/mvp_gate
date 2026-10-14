from __future__ import annotations

import re

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def check_branch_naming(ctx: CheckContext) -> CheckResult:
    check_id = "branch_naming"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    release_id = ctx.gate_input.release_id
    evidence: list[Evidence] = [
        Evidence(label="expected_branch", value=release_id),
    ]

    try:
        if ctx.gate_input.pr_id is not None and ctx.bitbucket.configured:
            pr = ctx.bitbucket.get_pr(ctx.gate_input.repository, ctx.gate_input.pr_id)
            from_ref = ((pr.get("fromRef") or {}).get("displayId")) or (
                (pr.get("fromRef") or {}).get("id") or ""
            )
            branch = str(from_ref).replace("refs/heads/", "")
            evidence.append(Evidence(label="pr_source_branch", value=branch))
            if branch == release_id or branch.endswith(f"/{release_id}"):
                return CheckResult(
                    check_id=check_id,
                    title=title,
                    status=CheckStatus.PASS,
                    summary=f"PR source branch matches release id {release_id}",
                    evidence=evidence,
                    policy=policy,
                )
            # Also accept feature branches targeting release branch
            to_ref = ((pr.get("toRef") or {}).get("displayId")) or ""
            to_branch = str(to_ref).replace("refs/heads/", "")
            evidence.append(Evidence(label="pr_target_branch", value=to_branch))
            if to_branch == release_id:
                return CheckResult(
                    check_id=check_id,
                    title=title,
                    status=CheckStatus.PASS,
                    summary=f"PR targets release branch {release_id}",
                    evidence=evidence,
                    policy=policy,
                )
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.BLOCK,
                summary=f"Neither source nor target branch matches release id {release_id}",
                evidence=evidence,
                policy=policy,
            )

        # Offline / no PR: validate release_id format
        if not re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", release_id):
            return CheckResult(
                check_id=check_id,
                title=title,
                status=CheckStatus.WARN,
                summary=f"Release id {release_id} does not look like a Jira key",
                evidence=evidence,
                policy=policy,
            )
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.PASS,
            summary=f"Release id {release_id} accepted (no PR context)",
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
