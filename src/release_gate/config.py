"""Environment and local config loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from release_gate.models import Catalog, GateMode


@dataclass
class ApiConfig:
    base_url: str = ""
    token: str = ""
    username: str = ""
    password: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2


@dataclass
class Settings:
    catalog_path: Path = Path("catalog/catalog.yaml")
    mode: GateMode = GateMode.SHADOW
    output_dir: Path = Path("artifacts")
    jira: ApiConfig = field(default_factory=ApiConfig)
    bitbucket: ApiConfig = field(default_factory=ApiConfig)
    confluence: ApiConfig = field(default_factory=ApiConfig)
    sonar: ApiConfig = field(default_factory=ApiConfig)
    dpm: ApiConfig = field(default_factory=ApiConfig)
    sast: ApiConfig = field(default_factory=ApiConfig)
    dry_run: bool = False
    # Legal Sonar exclusion path prefixes (yellow zone)
    legal_exclusion_prefixes: tuple[str, ...] = (
        "src/test/",
        "tests/",
        "**/mock/",
        "**/mocks/",
        "**/__mocks__/",
    )
    required_jira_fields: tuple[str, ...] = (
        "customfield_contour",
        "customfield_business_requirements",
    )
    report_marker: str = "<!-- release-gate:report -->"
    build_status_key: str = "release-gate"


def _api_from_env(prefix: str) -> ApiConfig:
    return ApiConfig(
        base_url=os.getenv(f"{prefix}_BASE_URL", ""),
        token=os.getenv(f"{prefix}_TOKEN", ""),
        username=os.getenv(f"{prefix}_USERNAME", ""),
        password=os.getenv(f"{prefix}_PASSWORD", ""),
        timeout_seconds=float(os.getenv(f"{prefix}_TIMEOUT", "30")),
        max_retries=int(os.getenv(f"{prefix}_RETRIES", "2")),
    )


def load_settings() -> Settings:
    mode_raw = os.getenv("RELEASE_GATE_MODE", "shadow").lower()
    mode = GateMode.ENFORCE if mode_raw == "enforce" else GateMode.SHADOW
    catalog = Path(os.getenv("RELEASE_GATE_CATALOG", "catalog/catalog.yaml"))
    output = Path(os.getenv("RELEASE_GATE_OUTPUT", "artifacts"))
    dry_run = os.getenv("RELEASE_GATE_DRY_RUN", "false").lower() in {"1", "true", "yes"}
    return Settings(
        catalog_path=catalog,
        mode=mode,
        output_dir=output,
        jira=_api_from_env("JIRA"),
        bitbucket=_api_from_env("BITBUCKET"),
        confluence=_api_from_env("CONFLUENCE"),
        sonar=_api_from_env("SONAR"),
        dpm=_api_from_env("DPM"),
        sast=_api_from_env("SAST"),
        dry_run=dry_run,
    )


def load_catalog(path: Path) -> Catalog:
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Catalog.model_validate(data)
