"""
Exa webhook JSON shapes.

Event catalog: https://docs.exa.ai/websets/api/events/types
Each event includes id, type, data (full resource), createdAt.

For `webset.item.enriched`, `data` is a Webset Item (see list-items OpenAPI):
https://docs.exa.ai/websets/api/websets/items/list-all-items-for-a-webset
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExaWebhookEvent(BaseModel):
    """Envelope for POST webhook body."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Unique event id")
    type: str = Field(description="e.g. webset.item.enriched")
    createdAt: str = Field(description="ISO8601 timestamp")
    data: dict[str, Any] = Field(description="Resource payload; for item events = WebsetItem")


def parse_webhook_event(body: dict[str, Any]) -> ExaWebhookEvent:
    return ExaWebhookEvent.model_validate(body)


def item_webset_id(item: dict[str, Any]) -> str | None:
    """WebsetItem.websetId"""
    v = item.get("websetId")
    return str(v).strip() if v else None


def item_id(item: dict[str, Any]) -> str | None:
    v = item.get("id")
    return str(v).strip() if v else None


def item_person_candidate_fields(item: dict[str, Any]) -> dict[str, str | None]:
    """
    Map WebsetItem (person) into flat fields for Ashby sync.

    Person properties live under data.properties (type=person) per Exa WebsetItem schema.
    Email may appear in enrichments (format email) — structure varies; caller can merge.
    """
    props = item.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    person = props.get("person") or {}
    if not isinstance(person, dict):
        person = {}

    name = person.get("name")
    name_s = str(name).strip() if name else None

    # Profile URL often on properties.url for person items
    url = props.get("url")
    linkedin = str(url).strip() if url else None
    if linkedin and "linkedin.com" not in linkedin.lower():
        linkedin = None

    email: str | None = None
    enrichments = item.get("enrichments")
    if isinstance(enrichments, list):
        for enr in enrichments:
            if not isinstance(enr, dict):
                continue
            if enr.get("format") != "email":
                continue
            status = enr.get("status")
            if status != "completed":
                continue
            result = enr.get("result")
            if isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, str) and first.strip():
                    email = first.strip().lower()
                    break
            if isinstance(result, str) and result.strip():
                email = result.strip().lower()
                break

    return {
        "name": name_s,
        "email": email,
        "linkedin_url": linkedin,
    }
