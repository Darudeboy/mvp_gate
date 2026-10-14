"""release-gate CLI entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from release_gate import __version__
from release_gate.config import load_settings
from release_gate.engine import ReleaseGateEngine, load_overrides
from release_gate.models import GateInput, GateMode, Phase
from release_gate.reporting.artifacts import write_artifacts
from release_gate.reporting.publisher import ReportPublisher
from release_gate.rules import RULE_MATRIX


def _parse_extra(extra: tuple[str, ...]) -> dict:
    result: dict = {}
    for item in extra:
        if "=" not in item:
            raise click.ClickException(f"Invalid --extra `{item}`, expected key=value or key=@file.json")
        key, value = item.split("=", 1)
        if value.startswith("@"):
            path = Path(value[1:])
            raw = path.read_text(encoding="utf-8")
            if path.suffix in {".yaml", ".yml"}:
                result[key] = yaml.safe_load(raw)
            else:
                result[key] = json.loads(raw)
        else:
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
    return result


@click.group()
@click.version_option(__version__)
def main() -> None:
    """MVP unified release control for Atlassian Data Center."""


@main.command("run")
@click.option("--release-id", required=True, help="Jira release issue key / branch name")
@click.option("--repository", required=True, help="Bitbucket repository as PROJECT/repo")
@click.option("--commit", required=True, help="Commit SHA")
@click.option("--pr-id", default=None, help="Pull request id (empty string allowed from CI)")
@click.option(
    "--phase",
    type=click.Choice(["pr", "release"], case_sensitive=False),
    default="pr",
)
@click.option(
    "--mode",
    type=click.Choice(["shadow", "enforce"], case_sensitive=False),
    default=None,
    help="Override RELEASE_GATE_MODE",
)
@click.option("--catalog", type=click.Path(path_type=Path), default=None)
@click.option("--output", type=click.Path(path_type=Path), default=None)
@click.option("--overrides", "overrides_path", type=click.Path(path_type=Path), default=None)
@click.option("--changed-file", "changed_files", multiple=True)
@click.option("--changed-files-from", type=click.Path(path_type=Path), default=None)
@click.option("--extra", multiple=True, help="key=value or key=@file.json")
@click.option("--publish/--no-publish", default=True)
@click.option("--dry-run/--no-dry-run", default=None)
@click.option("--build-url", default="https://ci.local/release-gate")
def run_cmd(
    release_id: str,
    repository: str,
    commit: str,
    pr_id: str | None,
    phase: str,
    mode: str | None,
    catalog: Path | None,
    output: Path | None,
    overrides_path: Path | None,
    changed_files: tuple[str, ...],
    changed_files_from: Path | None,
    extra: tuple[str, ...],
    publish: bool,
    dry_run: bool | None,
    build_url: str,
) -> None:
    """Run release-gate checks and write/publish the report."""
    settings = load_settings()
    if catalog:
        settings.catalog_path = catalog
    if output:
        settings.output_dir = output
    if dry_run is not None:
        settings.dry_run = dry_run

    resolved_pr: int | None = None
    if pr_id is not None and str(pr_id).strip():
        try:
            resolved_pr = int(str(pr_id).strip())
        except ValueError as exc:
            raise click.ClickException(f"Invalid --pr-id: {pr_id}") from exc

    resolved_mode = GateMode(mode) if mode else settings.mode
    files = list(changed_files)
    if changed_files_from and changed_files_from.exists():
        files.extend(
            line.strip()
            for line in changed_files_from.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    gate_input = GateInput(
        release_id=release_id,
        repository=repository,
        commit=commit,
        pr_id=resolved_pr,
        phase=Phase(phase.lower()),
        mode=resolved_mode,
        changed_files=files,
        extra=_parse_extra(extra),
    )
    overrides = load_overrides(overrides_path)

    engine = ReleaseGateEngine(settings)
    try:
        report = engine.run(gate_input, overrides=overrides)
        paths = write_artifacts(report, settings.output_dir, marker=settings.report_marker)
        publish_result = None
        if publish:
            publisher = ReportPublisher(settings, engine.bitbucket, engine.jira)
            publish_result = publisher.publish(report, paths, build_url=build_url)

        click.echo(report.model_dump_json(indent=2))
        click.echo(f"\nArtifacts: {settings.output_dir}", err=True)
        if publish_result:
            click.echo(f"Publish: {json.dumps(publish_result, default=str)}", err=True)
        sys.exit(report.exit_code())
    finally:
        engine.close()


@main.command("rules")
def rules_cmd() -> None:
    """Print the rule matrix."""
    serializable = {}
    for check_id, meta in RULE_MATRIX.items():
        serializable[check_id] = {
            **meta,
            "phases": [p.value if hasattr(p, "value") else p for p in meta["phases"]],
            "policy": meta["policy"].value if hasattr(meta["policy"], "value") else meta["policy"],
            "shadow_policy": meta["shadow_policy"].value
            if hasattr(meta["shadow_policy"], "value")
            else meta["shadow_policy"],
        }
    click.echo(json.dumps(serializable, indent=2))


@main.command("import-confluence")
@click.option("--page-id", required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
def import_confluence_cmd(page_id: str, out: Path) -> None:
    """Import Confluence owners table into a catalog YAML fragment."""
    from release_gate.adapters.confluence import ConfluenceAdapter

    settings = load_settings()
    adapter = ConfluenceAdapter(settings.confluence, dry_run=settings.dry_run)
    try:
        catalog = adapter.import_catalog_fragment(page_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(catalog.model_dump_json())
        out.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        click.echo(f"Wrote {out}")
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
