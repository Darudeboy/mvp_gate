"""Render PR comment and HTML report."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from release_gate.models import GateReport

STATUS_EMOJI = {
    "PASS": "GREEN",
    "WARN": "YELLOW",
    "BLOCK": "RED",
    "UNKNOWN": "GRAY",
}


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("release_gate", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_pr_comment(report: GateReport, *, marker: str) -> str:
    lines = [
        marker,
        f"## Release Gate — `{report.overall.value}` ({report.mode.value} / {report.phase.value})",
        "",
        f"- Release: **{report.release_id}**",
        f"- Repository: `{report.repository}`",
        f"- Commit: `{report.commit}`",
    ]
    if report.pr_id is not None:
        lines.append(f"- PR: `{report.pr_id}`")
    lines.append("")
    lines.append("| Status | Check | Summary |")
    lines.append("|--------|-------|---------|")
    overridden = {o.check_id: o for o in report.overrides}
    for check in report.checks:
        flag = STATUS_EMOJI.get(check.status.value, check.status.value)
        note = check.summary.replace("|", "/")
        if check.check_id in overridden:
            ov = overridden[check.check_id]
            note += f" _(override by {ov.approver}: {ov.reason})_"
        lines.append(f"| {flag} `{check.status.value}` | `{check.check_id}` | {note} |")
    if report.overrides:
        lines.append("")
        lines.append("### Manual overrides")
        for ov in report.overrides:
            lines.append(f"- `{ov.check_id}` by **{ov.approver}**: {ov.reason}")
    lines.append("")
    lines.append("_Idempotent report — updated in place by release-gate._")
    return "\n".join(lines)


def render_html(report: GateReport) -> str:
    template = _env().get_template("report.html.j2")
    return template.render(report=report, status_emoji=STATUS_EMOJI)


def render_markdown_file(report: GateReport, *, marker: str) -> str:
    return render_pr_comment(report, marker=marker)
