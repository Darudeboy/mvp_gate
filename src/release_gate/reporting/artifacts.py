"""Write JSON/HTML/Markdown artifacts to disk."""

from __future__ import annotations

from pathlib import Path

from release_gate.models import GateReport
from release_gate.reporting.render import render_html, render_markdown_file


def write_artifacts(report: GateReport, output_dir: Path, *, marker: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report.release_id}_{report.repository.replace('/', '_')}_{report.commit[:12]}"
    paths = {
        "json": output_dir / f"{stem}.json",
        "html": output_dir / f"{stem}.html",
        "md": output_dir / f"{stem}.md",
    }
    paths["json"].write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    paths["html"].write_text(render_html(report), encoding="utf-8")
    paths["md"].write_text(render_markdown_file(report, marker=marker), encoding="utf-8")
    # Stable latest pointers for CI
    (output_dir / "latest.json").write_text(paths["json"].read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / "latest.html").write_text(paths["html"].read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / "latest.md").write_text(paths["md"].read_text(encoding="utf-8"), encoding="utf-8")
    return paths
