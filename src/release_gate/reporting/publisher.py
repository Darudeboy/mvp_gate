"""Publish idempotent PR comment, build status and Jira artifacts."""

from __future__ import annotations

from pathlib import Path

from release_gate.adapters.base import AdapterError
from release_gate.adapters.bitbucket import BitbucketAdapter
from release_gate.adapters.jira import JiraAdapter
from release_gate.config import Settings
from release_gate.models import CheckStatus, GateReport
from release_gate.reporting.render import render_pr_comment


_STATUS_MAP = {
    CheckStatus.PASS: "SUCCESSFUL",
    CheckStatus.WARN: "SUCCESSFUL",
    CheckStatus.BLOCK: "FAILED",
    CheckStatus.UNKNOWN: "INPROGRESS",
}


class ReportPublisher:
    def __init__(
        self,
        settings: Settings,
        bitbucket: BitbucketAdapter,
        jira: JiraAdapter,
    ):
        self.settings = settings
        self.bitbucket = bitbucket
        self.jira = jira

    def publish(
        self,
        report: GateReport,
        artifact_paths: dict[str, Path],
        *,
        build_url: str = "https://ci.local/release-gate",
    ) -> dict:
        results: dict = {"pr_comment": None, "build_status": None, "jira_attachments": []}

        comment_body = render_pr_comment(report, marker=self.settings.report_marker)

        if report.pr_id is not None and self.bitbucket.configured:
            try:
                results["pr_comment"] = self.bitbucket.upsert_pr_comment(
                    report.repository,
                    report.pr_id,
                    comment_body,
                    marker=self.settings.report_marker,
                )
            except AdapterError as exc:
                results["pr_comment_error"] = str(exc)

            # In shadow mode always SUCCESSFUL so pipelines stay green
            state = "SUCCESSFUL"
            if report.mode.value == "enforce":
                state = _STATUS_MAP.get(report.overall, "FAILED")
                if report.exit_code() == 0 and report.overall != CheckStatus.BLOCK:
                    state = "SUCCESSFUL"
                elif report.exit_code() == 2:
                    state = "FAILED"
                elif report.exit_code() == 3:
                    state = "INPROGRESS"

            try:
                results["build_status"] = self.bitbucket.set_build_status(
                    report.commit,
                    key=self.settings.build_status_key,
                    state=state,
                    name="release-gate",
                    url=build_url,
                    description=f"{report.overall.value} ({report.mode.value})",
                )
            except AdapterError as exc:
                results["build_status_error"] = str(exc)

        if self.jira.configured:
            for kind, path in artifact_paths.items():
                mime = {
                    "json": "application/json",
                    "html": "text/html",
                    "md": "text/markdown",
                }.get(kind, "application/octet-stream")
                try:
                    attached = self.jira.attach_artifact(
                        report.release_id,
                        path.name,
                        path.read_bytes(),
                        mime,
                    )
                    results["jira_attachments"].append({"kind": kind, "result": attached})
                except AdapterError as exc:
                    results.setdefault("jira_errors", []).append({kind: str(exc)})

            # Short summary comment on the release issue
            try:
                self.jira.add_comment(
                    report.release_id,
                    f"release-gate {report.overall.value} for {report.repository}@{report.commit[:12]} "
                    f"(mode={report.mode.value}, phase={report.phase.value})",
                )
            except AdapterError as exc:
                results["jira_comment_error"] = str(exc)

        return results
