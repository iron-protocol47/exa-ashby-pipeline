from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.ashbyhq.com"
DEFAULT_TIMEOUT = 30.0


def _unwrap_results(data: dict[str, Any]) -> dict[str, Any] | None:
    r = data.get("results")
    return r if isinstance(r, dict) else None


def candidate_id_from_create_response(data: dict[str, Any]) -> str | None:
    """Parse candidate id from candidate.create JSON (shape varies slightly)."""
    results = _unwrap_results(data) or data
    if not isinstance(results, dict):
        return None
    cand = results.get("candidate")
    if isinstance(cand, dict):
        cid = cand.get("id")
        if isinstance(cid, str):
            return cid
    cid = results.get("id")
    if isinstance(cid, str):
        return cid
    return None


def build_candidate_create_body(
    *,
    name: str | None,
    email: str | None,
    linkedin_url: str | None,
) -> dict[str, Any]:
    """Body for POST /candidate.create — adjust if Ashby schema changes."""
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if email:
        body["emailAddresses"] = [{"value": email}]
    if linkedin_url:
        body["linkedinUrl"] = linkedin_url
    return body


class AshbyClient:
    """Ashby public API (RPC-style POST endpoints, Basic auth: API key as username)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(api_key, ""),
            headers={
                "Accept": "application/json; version=1",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AshbyClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def candidate_create(self, body: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post("/candidate.create", json=body)
        r.raise_for_status()
        return r.json()

    def application_create(
        self,
        *,
        candidate_id: str,
        job_id: str,
        credited_user_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "candidateId": candidate_id,
            "jobId": job_id,
        }
        if credited_user_id:
            payload["creditedUserId"] = credited_user_id
        r = self._client.post("/application.create", json=payload)
        r.raise_for_status()
        return r.json()

    def create_candidate_and_apply_to_job(
        self,
        *,
        job_id: str,
        name: str | None,
        email: str | None,
        linkedin_url: str | None,
        credited_user_id: str | None = None,
    ) -> str:
        """
        Create a candidate then attach an application to the job.
        Returns Ashby candidate id.
        """
        cand_body = build_candidate_create_body(
            name=name,
            email=email,
            linkedin_url=linkedin_url,
        )
        if not cand_body:
            raise ValueError("candidate.create requires at least one of name, email, linkedinUrl")
        created = self.candidate_create(cand_body)
        cid = candidate_id_from_create_response(created)
        if not cid:
            raise ValueError("candidate.create response missing candidate id")
        self.application_create(
            candidate_id=cid,
            job_id=job_id,
            credited_user_id=credited_user_id,
        )
        return cid
