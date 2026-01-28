from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import requests

from api.deps import get_current_user
from db.workspace_repo import MySQLWorkspaceRepo, WorkspaceRecord


router = APIRouter()
workspace_repo = MySQLWorkspaceRepo()

_ALLOWED_PLATFORMS = {"funpay", "playerok"}


def _mask_key(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 6:
        return "*" * len(raw)
    return f"{'*' * (len(raw) - 4)}{raw[-4:]}"


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform: str = Field("funpay", min_length=3, max_length=32)
    golden_key: str = Field(..., min_length=5)
    proxy_url: str = Field(..., min_length=3)
    is_default: bool = False


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    golden_key: str | None = Field(None, min_length=5)
    proxy_url: str | None = Field(None, min_length=3)
    is_default: bool | None = None


class WorkspaceItem(BaseModel):
    id: int
    name: str
    platform: str
    proxy_url: str
    is_default: bool
    created_at: str | None = None
    key_hint: str | None = None


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceItem]


class ProxyCheckResponse(BaseModel):
    ok: bool
    direct_ip: str | None = None
    proxy_ip: str | None = None
    error: str | None = None


_IP_CHECK_URL = "https://api.ipify.org?format=json"


def _fetch_ip(proxies: dict[str, str] | None = None) -> str:
    response = requests.get(_IP_CHECK_URL, timeout=10, proxies=proxies)
    response.raise_for_status()
    try:
        payload = response.json()
        ip_value = (payload.get("ip") if isinstance(payload, dict) else None) or ""
    except ValueError:
        ip_value = response.text or ""
    ip_value = str(ip_value).strip()
    if not ip_value:
        raise ValueError("IP response did not include an address.")
    return ip_value


def _to_item(record: WorkspaceRecord) -> WorkspaceItem:
    return WorkspaceItem(
        id=record.id,
        name=record.name,
        platform=record.platform,
        proxy_url=record.proxy_url,
        is_default=bool(record.is_default),
        created_at=record.created_at,
        key_hint=_mask_key(record.golden_key),
    )


@router.get("/workspaces", response_model=WorkspaceListResponse)
def list_workspaces(user=Depends(get_current_user)) -> WorkspaceListResponse:
    items = workspace_repo.list_by_user(int(user.id))
    return WorkspaceListResponse(items=[_to_item(item) for item in items])


@router.post("/workspaces", response_model=WorkspaceItem, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, user=Depends(get_current_user)) -> WorkspaceItem:
    name = payload.name.strip()
    platform = payload.platform.strip().lower()
    if platform not in _ALLOWED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported platform.")
    golden_key = payload.golden_key.strip()
    proxy_url = payload.proxy_url.strip()
    if not proxy_url:
        raise HTTPException(status_code=400, detail="Proxy is required for this workspace.")

    created = workspace_repo.create(
        user_id=int(user.id),
        name=name,
        platform=platform,
        golden_key=golden_key,
        proxy_url=proxy_url,
        is_default=payload.is_default,
    )
    if not created:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace already exists.")
    return _to_item(created)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceItem)
def update_workspace(workspace_id: int, payload: WorkspaceUpdate, user=Depends(get_current_user)) -> WorkspaceItem:
    existing = workspace_repo.get_by_id(workspace_id, int(user.id))
    if not existing:
        raise HTTPException(status_code=404, detail="Workspace not found")

    fields: dict = {}
    if payload.name is not None:
        fields["name"] = payload.name.strip()
    if payload.golden_key is not None and payload.golden_key.strip():
        fields["golden_key"] = payload.golden_key.strip()
    if payload.proxy_url is not None:
        proxy_url = payload.proxy_url.strip()
        if not proxy_url:
            raise HTTPException(status_code=400, detail="Proxy is required for this workspace.")
        fields["proxy_url"] = proxy_url

    make_default = payload.is_default is True
    if not fields and not make_default:
        raise HTTPException(status_code=400, detail="No changes provided")

    ok = workspace_repo.update(
        workspace_id=workspace_id,
        user_id=int(user.id),
        fields=fields,
        make_default=make_default,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update workspace")
    updated = workspace_repo.get_by_id(workspace_id, int(user.id))
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_item(updated)


@router.post("/workspaces/{workspace_id}/default")
def set_default_workspace(workspace_id: int, user=Depends(get_current_user)) -> dict:
    ok = workspace_repo.set_default(workspace_id, int(user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True}


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, user=Depends(get_current_user)) -> dict:
    ok = workspace_repo.delete(workspace_id, int(user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True}


@router.post("/workspaces/{workspace_id}/proxy-check", response_model=ProxyCheckResponse)
def check_workspace_proxy(workspace_id: int, user=Depends(get_current_user)) -> ProxyCheckResponse:
    existing = workspace_repo.get_by_id(workspace_id, int(user.id))
    if not existing:
        raise HTTPException(status_code=404, detail="Workspace not found")
    proxy_url = (existing.proxy_url or "").strip()
    if not proxy_url:
        return ProxyCheckResponse(ok=False, error="Proxy is not set for this workspace.")

    try:
        direct_ip = _fetch_ip()
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail="Failed to fetch direct IP address.")

    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        proxy_ip = _fetch_ip(proxies=proxies)
    except (requests.RequestException, ValueError):
        return ProxyCheckResponse(
            ok=False,
            direct_ip=direct_ip,
            proxy_ip=None,
            error="Proxy request failed.",
        )

    if proxy_ip == direct_ip:
        return ProxyCheckResponse(
            ok=False,
            direct_ip=direct_ip,
            proxy_ip=proxy_ip,
            error="Proxy did not change the IP address.",
        )
    return ProxyCheckResponse(ok=True, direct_ip=direct_ip, proxy_ip=proxy_ip)
