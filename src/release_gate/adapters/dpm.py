"""DPM adapter — KAE autofill / distribution registration gate."""

from __future__ import annotations

from typing import Any

from release_gate.adapters.base import HttpAdapter
from release_gate.config import ApiConfig


class DpmAdapter(HttpAdapter):
    name = "dpm"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    def resolve_kaes(self, release_id: str, services: list[str]) -> dict[str, Any]:
        """Ask DPM for KAE composition for a release.

        Expected response shape:
        {
          "release_id": "...",
          "kaes": ["KAE-1", ...],
          "missing_services": ["svc"],
          "blocked": false
        }
        """
        return self.request(
            "POST",
            "/api/v1/releases/resolve-kaes",
            json={"release_id": release_id, "services": services},
        )

    def can_register_distributions(self, release_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/releases/{release_id}/registration-status")
