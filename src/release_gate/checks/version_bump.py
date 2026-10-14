from __future__ import annotations

import re

from release_gate.checks.context import CheckContext
from release_gate.models import CheckResult, CheckStatus, Evidence
from release_gate.rules import RULE_MATRIX, effective_policy

VERSION_FILE_HINTS = (
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "Chart.yaml",
    "VERSION",
    "version.txt",
)


def check_version_bump(ctx: CheckContext) -> CheckResult:
    check_id = "version_bump"
    title = RULE_MATRIX[check_id]["title"]
    policy = effective_policy(check_id, ctx.gate_input.mode)
    files = ctx.changed_files()
    evidence = [Evidence(label="changed_files_count", value=str(len(files)))]

    touched = [f for f in files if any(f.endswith(h) or f == h for h in VERSION_FILE_HINTS)]
    # Also catch version bumps inside paths
    versionish = [
        f
        for f in files
        if re.search(r"version", f, re.I) and f.endswith((".yml", ".yaml", ".properties", ".toml"))
    ]
    bumped = sorted(set(touched + versionish))
    evidence.append(Evidence(label="version_files", value=",".join(bumped) or "(none)"))

    if not files:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.UNKNOWN,
            summary="No changed files available to detect version bump",
            evidence=evidence,
            policy=policy,
        )

    if bumped:
        return CheckResult(
            check_id=check_id,
            title=title,
            status=CheckStatus.PASS,
            summary=f"Version-related files changed: {', '.join(bumped)}",
            evidence=evidence,
            policy=policy,
        )

    return CheckResult(
        check_id=check_id,
        title=title,
        status=CheckStatus.WARN,
        summary="No version file changes detected on release phase",
        evidence=evidence,
        policy=policy,
    )
