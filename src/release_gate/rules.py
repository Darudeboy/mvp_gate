"""Matrix of blocking / warning / observe rules for MVP phases."""

from __future__ import annotations

from release_gate.models import GateMode, Phase, SeverityPolicy


# check_id -> (title, default policy in enforce, shadow policy notes)
RULE_MATRIX: dict[str, dict] = {
    "branch_naming": {
        "title": "Release branch naming matches Jira release id",
        "phases": [Phase.PR, Phase.RELEASE],
        "policy": SeverityPolicy.BLOCK,
        "shadow_policy": SeverityPolicy.WARN,
        "sources": ["Bitbucket branch", "Jira release issue"],
    },
    "required_fields": {
        "title": "Required Jira fields (contour label, business requirements)",
        "phases": [Phase.PR, Phase.RELEASE],
        "policy": SeverityPolicy.BLOCK,
        "shadow_policy": SeverityPolicy.WARN,
        "sources": ["Jira issue fields"],
    },
    "service_kae_binding": {
        "title": "Service bound to KAE and present in release composition",
        "phases": [Phase.PR, Phase.RELEASE],
        "policy": SeverityPolicy.BLOCK,
        "shadow_policy": SeverityPolicy.BLOCK,
        "sources": ["Catalog", "Jira release", "DPM", "Project Config"],
    },
    "catalog_consistency": {
        "title": "Jira / Project Config / catalog naming consistency",
        "phases": [Phase.PR, Phase.RELEASE],
        "policy": SeverityPolicy.WARN,
        "shadow_policy": SeverityPolicy.WARN,
        "sources": ["Catalog", "Project Config", "Jira"],
    },
    "sonar_exclusions": {
        "title": "SonarQube exclusion traffic light for changed files",
        "phases": [Phase.PR],
        "policy": SeverityPolicy.WARN,
        "shadow_policy": SeverityPolicy.OBSERVE,
        "sources": ["Bitbucket PR diff", "SonarQube exclusions API"],
    },
    "sast_dependencies": {
        "title": "SAST / dependency findings for release composition",
        "phases": [Phase.RELEASE, Phase.PR],
        "policy": SeverityPolicy.WARN,
        "shadow_policy": SeverityPolicy.OBSERVE,
        "sources": ["SAST report", "dependency scan"],
    },
    "version_bump": {
        "title": "Service version bumped on release branch",
        "phases": [Phase.RELEASE],
        "policy": SeverityPolicy.WARN,
        "shadow_policy": SeverityPolicy.OBSERVE,
        "sources": ["Bitbucket release branch", "version files"],
    },
    "approvals": {
        "title": "Required reviewers / lead approvals present",
        "phases": [Phase.PR, Phase.RELEASE],
        "policy": SeverityPolicy.WARN,
        "shadow_policy": SeverityPolicy.OBSERVE,
        "sources": ["Bitbucket PR reviewers"],
    },
}


def effective_policy(check_id: str, mode: GateMode) -> SeverityPolicy:
    rule = RULE_MATRIX.get(check_id)
    if not rule:
        return SeverityPolicy.WARN
    if mode == GateMode.SHADOW:
        return rule.get("shadow_policy", SeverityPolicy.OBSERVE)
    return rule.get("policy", SeverityPolicy.WARN)


def checks_for_phase(phase: Phase) -> list[str]:
    return [
        check_id
        for check_id, meta in RULE_MATRIX.items()
        if phase in meta["phases"]
    ]
