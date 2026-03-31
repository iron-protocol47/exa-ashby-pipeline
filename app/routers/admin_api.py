from __future__ import annotations

import hmac
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from app.ashby.client import AshbyClient, projects_from_list_response
from app.config import Settings, get_settings
from app.db.connection import connection_context
from app.db.models import Mapping
from app.db.repositories import MappingRepository

router = APIRouter(prefix="/api", tags=["admin"])
security = HTTPBasic(auto_error=False)


def _admin_configured(settings: Settings) -> bool:
    return bool(
        (settings.admin_basic_user or "").strip()
        and (settings.admin_basic_password or "").strip()
    )


def verify_admin(
    credentials: Annotated[Optional[HTTPBasicCredentials], Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not _admin_configured(settings):
        raise HTTPException(
            status_code=503,
            detail="Admin HTTP Basic is not configured (ADMIN_BASIC_USER / ADMIN_BASIC_PASSWORD)",
        )
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )
    u = (settings.admin_basic_user or "").strip()
    p = (settings.admin_basic_password or "").strip()
    user_ok = hmac.compare_digest(credentials.username, u)
    pass_ok = hmac.compare_digest(credentials.password, p)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _mapping_to_dict(m: Mapping) -> dict:
    return {
        "id": m.id,
        "websetId": m.webset_id,
        "ashbyProjectId": m.ashby_project_id,
        "sourceTag": m.source_tag,
        "active": m.active,
        "exaWebhookId": m.exa_webhook_id,
        "candidatesPushedCount": m.candidates_pushed_count,
        "lastSyncAt": m.last_sync_at,
        "createdAt": m.created_at,
        "updatedAt": m.updated_at,
    }


class MappingCreate(BaseModel):
    webset_id: str = Field(min_length=1)
    ashby_project_id: str = Field(min_length=1)
    source_tag: str = Field(min_length=1)
    active: bool = True
    exa_webhook_id: Optional[str] = None


class MappingUpdate(BaseModel):
    ashby_project_id: Optional[str] = None
    source_tag: Optional[str] = None
    active: Optional[bool] = None


@router.get("/ashby/projects")
def list_ashby_projects(
    _: Annotated[None, Depends(verify_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    key = (settings.ashby_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="ASHBY_API_KEY is not set",
        )
    try:
        with AshbyClient(key) as client:
            raw = client.project_list()
    except httpx.HTTPStatusError as e:
        detail = f"Ashby HTTP {e.response.status_code}"
        try:
            detail = f"{detail}: {e.response.text[:500]}"
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=detail) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Ashby request failed: {e}") from e
    return {"projects": projects_from_list_response(raw)}


@router.get("/mappings")
def list_mappings(
    _: Annotated[None, Depends(verify_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    with connection_context(settings.database_path) as conn:
        repo = MappingRepository(conn)
        items = repo.list_all()
    return {"mappings": [_mapping_to_dict(m) for m in items]}


@router.post("/mappings")
def create_mapping(
    body: MappingCreate,
    _: Annotated[None, Depends(verify_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    with connection_context(settings.database_path) as conn:
        repo = MappingRepository(conn)
        mid = repo.create(
            webset_id=body.webset_id,
            ashby_project_id=body.ashby_project_id,
            source_tag=body.source_tag,
            active=body.active,
            exa_webhook_id=body.exa_webhook_id,
        )
        m = repo.get_by_id(mid)
    if m is None:
        raise HTTPException(status_code=500, detail="Failed to read mapping after insert")
    return _mapping_to_dict(m)


@router.patch("/mappings/{mapping_id}")
def update_mapping(
    mapping_id: int,
    body: MappingUpdate,
    _: Annotated[None, Depends(verify_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if (
        body.ashby_project_id is None
        and body.source_tag is None
        and body.active is None
    ):
        raise HTTPException(status_code=400, detail="No fields to update")
    with connection_context(settings.database_path) as conn:
        repo = MappingRepository(conn)
        existing = repo.get_by_id(mapping_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Mapping not found")
        if body.ashby_project_id is not None and not body.ashby_project_id.strip():
            raise HTTPException(status_code=400, detail="ashby_project_id cannot be empty")
        if body.source_tag is not None and not body.source_tag.strip():
            raise HTTPException(status_code=400, detail="source_tag cannot be empty")
        repo.update(
            mapping_id,
            ashby_project_id=body.ashby_project_id,
            source_tag=body.source_tag,
            active=body.active,
        )
        m = repo.get_by_id(mapping_id)
    if m is None:
        raise HTTPException(status_code=500, detail="Failed to read mapping after update")
    return _mapping_to_dict(m)


@router.delete("/mappings/{mapping_id}")
def delete_mapping(
    mapping_id: int,
    _: Annotated[None, Depends(verify_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    with connection_context(settings.database_path) as conn:
        repo = MappingRepository(conn)
        existing = repo.get_by_id(mapping_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Mapping not found")
        repo.delete(mapping_id)
    return {"ok": True, "deletedId": mapping_id}
