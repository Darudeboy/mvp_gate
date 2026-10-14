"""SonarQube adapter for exclusion traffic-light."""

from __future__ import annotations

from typing import Any

from release_gate.adapters.base import HttpAdapter
from release_gate.config import ApiConfig


class SonarAdapter(HttpAdapter):
    name = "sonar"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    def get_exclusions(self, component_key: str) -> list[str]:
        """Return coverage/exclusions patterns for a component.

        Uses Sonar settings API; falls back to empty list when unset.
        """
        data = self.request(
            "GET",
            "/api/settings/values",
            params={
                "component": component_key,
                "keys": "sonar.coverage.exclusions,sonar.exclusions,sonar.cpd.exclusions",
            },
        )
        patterns: list[str] = []
        for setting in data.get("settings") or []:
            value = setting.get("value") or ""
            if value:
                patterns.extend(p.strip() for p in value.split(",") if p.strip())
            for v in setting.get("values") or []:
                if v:
                    patterns.append(str(v).strip())
        return sorted(set(patterns))

    def get_quality_gate_status(self, component_key: str) -> dict[str, Any]:
        return self.request(
            "GET",
            "/api/qualitygates/project_status",
            params={"projectKey": component_key},
        )
