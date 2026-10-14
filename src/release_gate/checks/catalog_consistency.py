from __future__ import annotations

from release_gate.adapters.base import AdapterError
from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy


def check_catalog_consistency(ctx: CheckContext) -> CheckResult:
    check_id = "catalog_consistency"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    evidence: list[Evidence] = []
    mismatches: list[str] = []

    svc = ctx.catalog.service_by_repo(ctx.gate_input.repository)
    if not svc:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary="Repository missing from catalog (no silent fix applied)",
            evidence=[Evidence(label="repository", value=ctx.gate_input.repository)],
            policy=policy,
        )

    evidence.append(Evidence(label="catalog_service", value=svc.service_id))
    evidence.append(Evidence(label="catalog_repository", value=svc.repository or ""))

    # Project Config may be provided via gate_input.extra["project_config"]
    pc = (ctx.gate_input.extra or {}).get("project_config") or {}
    pc_service = pc.get("service_id") or pc.get("service")
    pc_kae = pc.get("kae_id") or pc.get("kae")
    pc_repo = pc.get("repository")

    if pc_repo and svc.repository and pc_repo.lower().rstrip("/") != svc.repository.lower().rstrip("/"):
        mismatches.append("repository")
        evidence.append(Evidence(label="project_config_repository", value=str(pc_repo)))

    if pc_service and pc_service not in {svc.service_id, svc.name}:
        mismatches.append("service_id")
        evidence.append(Evidence(label="project_config_service", value=str(pc_service)))

    if pc_kae and pc_kae not in svc.kae_ids:
        mismatches.append("kae_id")
        evidence.append(Evidence(label="project_config_kae", value=str(pc_kae)))

    # Soft check against Jira naming when composition present
    try:
        issue = ctx.release_issue()
        if issue:
            release_services = issue.get("services") or []
            if release_services and svc.service_id not in release_services and svc.name not in release_services:
                # Not necessarily a mismatch of naming — just note it
                evidence.append(
                    Evidence(
                        label="jira_release_services",
                        value=",".join(map(str, release_services)),
                    )
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

    # Data quality heuristics: placeholder owners
    bad_owners = {"voice of employee", "tbd", "todo", "n/a", "-"}
    if svc.pio and svc.pio.strip().lower() in bad_owners:
        mismatches.append("pio_placeholder")
        evidence.append(Evidence(label="pio", value=svc.pio))

    if mismatches:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.WARN,
            summary=f"Explicit mismatches (no auto-fix): {', '.join(mismatches)}",
            evidence=evidence,
            policy=policy,
            details={"mismatches": mismatches},
        )

    return CheckResult(
        check_id=check_id,
        title=title,
        status=CheckStatus.PASS,
        summary="Catalog / Project Config / Jira naming consistent",
        evidence=evidence,
        policy=policy,
    )
