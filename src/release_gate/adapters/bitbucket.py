"""Bitbucket Data Center adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from release_gate.adapters.base import AdapterError, HttpAdapter
from release_gate.config import ApiConfig


class BitbucketAdapter(HttpAdapter):
    name = "bitbucket"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    @staticmethod
    def split_repo(repository: str) -> tuple[str, str]:
        # Accept "PROJ/repo" or "proj/repo.git"
        cleaned = repository.strip().rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        if "/" not in cleaned:
            raise AdapterError(f"Invalid repository id: {repository}", transient=False)
        project, repo = cleaned.split("/", 1)
        return project, repo

    def get_pr(self, repository: str, pr_id: int) -> dict[str, Any]:
        project, repo = self.split_repo(repository)
        return self.request(
            "GET",
            f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}/pull-requests/{pr_id}",
        )

    def list_pr_changed_files(self, repository: str, pr_id: int) -> list[str]:
        project, repo = self.split_repo(repository)
        path = (
            f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}"
            f"/pull-requests/{pr_id}/changes"
        )
        data = self.request("GET", path, params={"limit": 1000})
        files: list[str] = []
        for item in data.get("values") or []:
            path_obj = item.get("path") or {}
            to_string = path_obj.get("toString") or item.get("path", {}).get("name")
            if to_string:
                files.append(to_string)
        return files

    def list_pr_comments(self, repository: str, pr_id: int) -> list[dict[str, Any]]:
        project, repo = self.split_repo(repository)
        data = self.request(
            "GET",
            f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}"
            f"/pull-requests/{pr_id}/activities",
            params={"limit": 100},
        )
        comments: list[dict[str, Any]] = []
        for activity in data.get("values") or []:
            if activity.get("action") == "COMMENTED" and activity.get("comment"):
                comments.append(activity["comment"])
        return comments

    def upsert_pr_comment(
        self,
        repository: str,
        pr_id: int,
        body: str,
        *,
        marker: str,
    ) -> dict[str, Any]:
        project, repo = self.split_repo(repository)
        existing_id: int | None = None
        existing_version: int = 0
        try:
            for comment in self.list_pr_comments(repository, pr_id):
                text = comment.get("text") or ""
                if marker in text:
                    existing_id = comment.get("id")
                    existing_version = int(comment.get("version") or 0)
                    break
        except AdapterError:
            existing_id = None

        if existing_id is not None:
            return self.request(
                "PUT",
                f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}"
                f"/pull-requests/{pr_id}/comments/{existing_id}",
                json={"text": body, "version": existing_version},
            )
        return self.request(
            "POST",
            f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}"
            f"/pull-requests/{pr_id}/comments",
            json={"text": body},
        )

    def set_build_status(
        self,
        commit: str,
        *,
        key: str,
        state: str,
        name: str,
        url: str,
        description: str,
    ) -> dict[str, Any]:
        # Bitbucket DC build-status API
        return self.request(
            "POST",
            f"/rest/build-status/1.0/commits/{commit}",
            json={
                "state": state,
                "key": key,
                "name": name,
                "url": url,
                "description": description[:255],
            },
        )

    def get_reviewers(self, repository: str, pr_id: int) -> list[dict[str, Any]]:
        pr = self.get_pr(repository, pr_id)
        return list(pr.get("reviewers") or [])
