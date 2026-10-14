"""Jira Data Center adapter."""

from __future__ import annotations

from typing import Any

from release_gate.adapters.base import AdapterError, HttpAdapter
from release_gate.config import ApiConfig


class JiraAdapter(HttpAdapter):
    name = "jira"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self.request("GET", f"/rest/api/2/issue/{issue_key}", params=params)

    def get_release_composition(self, release_id: str) -> dict[str, Any]:
        """Return services/KAEs linked to the release issue.

        Expected custom fields (configurable environment):
        - customfield_release_services
        - customfield_release_kaes
        """
        issue = self.get_issue(
            release_id,
            fields=[
                "summary",
                "labels",
                "issuelinks",
                "customfield_contour",
                "customfield_business_requirements",
                "customfield_release_services",
                "customfield_release_kaes",
            ],
        )
        fields = issue.get("fields") or {}
        services = _as_id_list(fields.get("customfield_release_services"))
        kaes = _as_id_list(fields.get("customfield_release_kaes"))
        return {
            "key": issue.get("key", release_id),
            "summary": fields.get("summary"),
            "labels": fields.get("labels") or [],
            "contour": fields.get("customfield_contour"),
            "business_requirements": fields.get("customfield_business_requirements"),
            "services": services,
            "kaes": kaes,
            "raw": fields,
        }

    def attach_artifact(self, issue_key: str, filename: str, content: bytes, mime: str) -> dict[str, Any]:
        if self.dry_run:
            return {"dry_run": True, "issue": issue_key, "filename": filename}
        if not self.configured:
            raise AdapterError("jira is not configured", transient=False)
        # Multipart attachment endpoint
        files = {"file": (filename, content, mime)}
        headers = {"X-Atlassian-Token": "no-check"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        client = self.client()
        response = client.post(
            f"/rest/api/2/issue/{issue_key}/attachments",
            files=files,
            headers=headers,
        )
        if response.status_code >= 400:
            raise AdapterError(
                f"jira attach failed: {response.status_code}",
                transient=response.status_code >= 500,
                status_code=response.status_code,
            )
        return response.json()

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        return self.request("POST", f"/rest/api/2/issue/{issue_key}/comment", json={"body": body})


def _as_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(str(item.get("value") or item.get("id") or item.get("name") or item))
            else:
                result.append(str(item))
        return result
    if isinstance(value, dict):
        return [str(value.get("value") or value.get("id") or value)]
    return [str(value)]
