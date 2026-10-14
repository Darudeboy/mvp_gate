"""SAST / dependency scan adapter."""

from __future__ import annotations

from typing import Any

from release_gate.adapters.base import HttpAdapter
from release_gate.config import ApiConfig


class SastAdapter(HttpAdapter):
    name = "sast"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    def get_findings(self, repository: str, commit: str) -> dict[str, Any]:
        """Fetch SAST findings for a commit.

        Expected response:
        {
          "findings": [
            {"id": "...", "severity": "HIGH|MEDIUM|LOW", "title": "...", "component": "..."}
          ]
        }
        """
        return self.request(
            "GET",
            "/api/v1/findings",
            params={"repository": repository, "commit": commit},
        )
