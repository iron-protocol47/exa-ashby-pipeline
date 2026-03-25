from __future__ import annotations

import hmac
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

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
        "ashbyJobId": m.ashby_job_id,
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
    ashby_job_id: str = Field(min_length=1)
    source_tag: str = Field(min_length=1)
    active: bool = True
    exa_webhook_id: Optional[str] = None


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
            ashby_job_id=body.ashby_job_id,
            source_tag=body.source_tag,
            active=body.active,
            exa_webhook_id=body.exa_webhook_id,
        )
        m = repo.get_by_id(mid)
    if m is None:
        raise HTTPException(status_code=500, detail="Failed to read mapping after insert")
    return _mapping_to_dict(m)
