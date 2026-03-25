from __future__ import annotations

from typing import Any, Iterator

import httpx

DEFAULT_BASE_URL = "https://api.exa.ai/websets"
DEFAULT_TIMEOUT = 30.0

ITEM_ENRICHED = "webset.item.enriched"


class ExaClient:
    """
    Exa Websets HTTP API (x-api-key auth).

    Base URL: https://api.exa.ai/websets — paths like /v0/websets
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"x-api-key": api_key},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ExaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def list_websets(
        self, *, limit: int = 100, cursor: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = self._client.get("/v0/websets", params=params)
        r.raise_for_status()
        return r.json()

    def iter_websets(self, *, page_size: int = 100) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            page = self.list_websets(limit=page_size, cursor=cursor)
            for row in page.get("data") or []:
                if isinstance(row, dict):
                    yield row
            if not page.get("hasMore"):
                break
            cursor = page.get("nextCursor")
            if not cursor:
                break

    def list_items(
        self,
        webset_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if cursor:
            params["cursor"] = cursor
        r = self._client.get(f"/v0/websets/{webset_id}/items", params=params)
        r.raise_for_status()
        return r.json()

    def iter_items(self, webset_id: str, *, page_size: int = 100) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            page = self.list_items(webset_id, limit=page_size, cursor=cursor)
            for row in page.get("data") or []:
                if isinstance(row, dict):
                    yield row
            if not page.get("hasMore"):
                break
            cursor = page.get("nextCursor")
            if not cursor:
                break

    def create_webhook(
        self,
        *,
        url: str,
        events: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "url": url,
            "events": events if events is not None else [ITEM_ENRICHED],
        }
        if metadata:
            body["metadata"] = metadata
        r = self._client.post("/v0/webhooks", json=body)
        r.raise_for_status()
        return r.json()

    def delete_webhook(self, webhook_id: str) -> dict[str, Any]:
        r = self._client.delete(f"/v0/webhooks/{webhook_id}")
        r.raise_for_status()
        return r.json()

    def patch_webhook(self, webhook_id: str, body: dict[str, Any]) -> dict[str, Any]:
        r = self._client.patch(f"/v0/webhooks/{webhook_id}", json=body)
        r.raise_for_status()
        return r.json()

    def set_webhook_status(self, webhook_id: str, *, active: bool) -> dict[str, Any]:
        """
        Set webhook active/inactive. Exa documents status on the Webhook model; if PATCH
        rejects `status`, callers should fall back to DB-side gating only.
        """
        status = "active" if active else "inactive"
        return self.patch_webhook(webhook_id, {"status": status})
