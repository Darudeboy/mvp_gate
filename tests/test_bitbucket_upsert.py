from __future__ import annotations

from release_gate.adapters.bitbucket import BitbucketAdapter
from release_gate.config import ApiConfig


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if "activities" in path and method == "GET":
            return {
                "values": [
                    {
                        "action": "COMMENTED",
                        "comment": {
                            "id": 99,
                            "text": "<!-- release-gate:report -->\nold",
                            "version": 3,
                        },
                    }
                ]
            }
        return {"ok": True}


def test_upsert_updates_existing_comment(monkeypatch) -> None:
    adapter = BitbucketAdapter(ApiConfig(base_url="https://bitbucket.example"), dry_run=False)
    fake = FakeClient()

    def fake_request(method, path, **kwargs):
        return fake.request(method, path, **kwargs)

    monkeypatch.setattr(adapter, "request", fake_request)
    result = adapter.upsert_pr_comment(
        "PAY/payments-api",
        7,
        "<!-- release-gate:report -->\nnew",
        marker="<!-- release-gate:report -->",
    )
    assert result["ok"] is True
    methods = [c[0] for c in fake.calls]
    assert "GET" in methods
    assert "PUT" in methods
