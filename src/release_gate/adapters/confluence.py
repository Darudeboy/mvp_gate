"""Confluence Data Center adapter — import owners table into catalog."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from release_gate.adapters.base import HttpAdapter
from release_gate.config import ApiConfig
from release_gate.models import Catalog, EscalationContact, ServiceRecord


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            text = " ".join(self._current_cell).strip()
            self._current_row.append(re.sub(r"\s+", " ", text))
            self._current_cell = None
            self._in_cell = False
        elif tag == "tr" and self._current_row is not None:
            if any(self._current_row):
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(data)


class ConfluenceAdapter(HttpAdapter):
    name = "confluence"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)

    def get_page_storage(self, page_id: str) -> str:
        data = self.request(
            "GET",
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage"},
        )
        return ((data.get("body") or {}).get("storage") or {}).get("value") or ""

    def parse_owners_table(self, html: str) -> list[dict[str, str]]:
        parser = _TableParser()
        parser.feed(html)
        if not parser.rows:
            return []
        headers = [h.strip().lower() for h in parser.rows[0]]
        records: list[dict[str, str]] = []
        for row in parser.rows[1:]:
            item: dict[str, str] = {}
            for idx, header in enumerate(headers):
                if idx < len(row):
                    item[header] = row[idx]
            if item:
                records.append(item)
        return records

    def import_catalog_fragment(self, page_id: str) -> Catalog:
        """Build a partial catalog from Confluence owners matrix."""
        html = self.get_page_storage(page_id)
        rows = self.parse_owners_table(html)
        services: list[ServiceRecord] = []
        for row in rows:
            name = row.get("service") or row.get("сервис") or row.get("name")
            if not name:
                continue
            service_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            pio = row.get("pio") or row.get("owner") or row.get("лид")
            delivery = row.get("delivery") or row.get("доставка")
            cluster = row.get("cluster") or row.get("кластер")
            impact = row.get("impact") or row.get("импакт")
            repository = row.get("repository") or row.get("repo") or row.get("репозиторий")
            escalation = [
                EscalationContact(role="PIO", name=pio, email=None),
            ]
            if delivery:
                escalation.append(EscalationContact(role="Delivery", name=delivery, email=None))
            services.append(
                ServiceRecord(
                    service_id=service_id,
                    name=name,
                    cluster=cluster,
                    impact=impact,
                    pio=pio,
                    delivery=delivery,
                    repository=repository,
                    escalation=escalation,
                )
            )
        return Catalog(version="1", source=f"confluence:{page_id}", services=services, kaes=[])
