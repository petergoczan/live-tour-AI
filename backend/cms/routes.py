"""
Admin CMS UI: Jinja2-rendered dashboard and partner details.

The CMS uses the core storage layer directly instead of calling internal HTTP APIs.
"""
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from markupsafe import Markup

from core import storage
from core.schemas import Marker, Partner


router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _tojson(value):
    """Jinja2 filter: serialize to JSON for HTML data attributes (safe string)."""

    if hasattr(value, "model_dump"):
        value = value.model_dump()
    # Mark as safe so the JSON isn't HTML-escaped inside <script> blocks.
    return Markup(json.dumps(value))


templates.env.filters["tojson"] = _tojson


class PartnerCreateBody(BaseModel):
    name: str = Field(..., min_length=3, max_length=15)


class MarkerBody(BaseModel):
    name_en: Optional[str] = None
    name_hu: Optional[str] = None
    origin_name: Optional[str] = None
    lat: float
    lng: float


class GlobalConfigBody(BaseModel):
    personas: list[str]
    languages: list[str]


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, lang: str = "EN"):
    """Dashboard: partners list and add partner."""

    partners = storage.get_partners()
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "partners": partners, "lang": lang.upper()},
    )


@router.post("/partners", response_class=JSONResponse)
async def create_partner(body: PartnerCreateBody):
    """Create a new partner from the dashboard modal."""

    partner = Partner(id=str(uuid.uuid4()), name=body.name.strip())
    storage.save_partner(partner)
    return partner.model_dump()


@router.get("/partner/{partner_id}", response_class=HTMLResponse)
async def partner_detail(request: Request, partner_id: str, lang: str = "EN"):
    """Partner details: markers list and add/edit marker."""

    partners = storage.get_partners()
    partner = next((p for p in partners if p.id == partner_id), None)
    if not partner:
        return templates.TemplateResponse(
            "admin_partner_not_found.html",
            {"request": request, "partner_id": partner_id, "lang": lang.upper()},
        )
    markers = storage.get_markers_by_partner(partner_id)
    config = storage.get_global_config()
    return templates.TemplateResponse(
        "admin_partner_detail.html",
        {
            "request": request,
            "partner": partner,
            "markers": markers,
            "config": config,
            "lang": lang.upper(),
        },
    )


@router.post("/partner/{partner_id}/markers", response_class=JSONResponse)
async def add_marker(partner_id: str, body: MarkerBody):
    """Add a marker for a partner."""

    partners = storage.get_partners()
    if not any(p.id == partner_id for p in partners):
        raise HTTPException(status_code=404, detail="Partner not found")
    name_en = (body.name_en or "").strip()
    name_hu = (body.name_hu or "").strip()
    origin_name = (body.origin_name or "").strip()
    if not (name_en or name_hu or origin_name):
        raise HTTPException(
            status_code=400,
            detail="At least one of name_en, name_hu, or origin_name must be provided",
        )
    # Prevent duplicates for this partner by name (any language/origin) or exact lat/lng.
    existing_markers = storage.get_markers_by_partner(partner_id)
    for m in existing_markers:
        if name_hu and (m.name_hu or "").strip() == name_hu:
            raise HTTPException(
                status_code=400,
                detail=f"There is already a marker saved with that Hungarian name: {name_hu}",
            )
        if name_en and (m.name_en or "").strip() == name_en:
            raise HTTPException(
                status_code=400,
                detail=f"There is already a marker saved with that English name: {name_en}",
            )
        if origin_name and (m.origin_name or "").strip() == origin_name:
            raise HTTPException(
                status_code=400,
                detail=f"There is already a marker saved with that original name: {origin_name}",
            )
        if m.lat == body.lat and m.lng == body.lng:
            raise HTTPException(
                status_code=400,
                detail=f"There is already a marker saved with that position: ({body.lat}, {body.lng})",
            )
    marker = Marker(
        id=str(uuid.uuid4()),
        lat=body.lat,
        lng=body.lng,
        name_en=name_en or None,
        name_hu=name_hu or None,
        origin_name=origin_name or None,
    )
    existing_markers.append(marker)
    storage.save_markers_for_partner(partner_id, existing_markers)
    return marker.model_dump()


@router.put("/partner/{partner_id}/markers/{marker_id}", response_class=JSONResponse)
async def update_marker(partner_id: str, marker_id: str, body: MarkerBody):
    """Update an existing marker for a partner."""

    partners = storage.get_partners()
    if not any(p.id == partner_id for p in partners):
        raise HTTPException(status_code=404, detail="Partner not found")
    markers = storage.get_markers_by_partner(partner_id)
    existing = next((m for m in markers if m.id == marker_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Marker not found")
    updated = Marker(
        id=marker_id,
        lat=body.lat,
        lng=body.lng,
        name_en=body.name_en or None,
        name_hu=body.name_hu or None,
        origin_name=body.origin_name or None,
    )
    new_list = [m if m.id != marker_id else updated for m in markers]
    storage.save_markers_for_partner(partner_id, new_list)
    return updated.model_dump()


@router.delete("/partner/{partner_id}/markers/{marker_id}", response_class=JSONResponse)
async def delete_marker(partner_id: str, marker_id: str):
    """Delete a marker for a partner from the admin UI."""

    partners = storage.get_partners()
    if not any(p.id == partner_id for p in partners):
        raise HTTPException(status_code=404, detail="Partner not found")
    markers = storage.get_markers_by_partner(partner_id)
    if not any(m.id == marker_id for m in markers):
        raise HTTPException(status_code=404, detail="Marker not found")
    new_list = [m for m in markers if m.id != marker_id]
    storage.save_markers_for_partner(partner_id, new_list)
    return {"status": "deleted", "marker_id": marker_id}


# --- Content store (facts) ---


@router.get("/config")
def get_config():
    return storage.get_global_config()


@router.put("/config")
def put_config(body: GlobalConfigBody):
    storage.save_global_config({"personas": body.personas, "languages": body.languages})
    return storage.get_global_config()


@router.get("/content/{marker_id}")
def get_marker_content(marker_id: str):
    """Return content store slice for one marker: { persona: { lang: [str, ...] } }."""
    store = storage.get_content_store()
    if marker_id not in store:
        raise HTTPException(status_code=404, detail="Marker not found or no content")
    return store[marker_id]


@router.put("/content/{marker_id}")
def save_marker_content(marker_id: str, content: dict):
    """Save content for one marker (overwrites existing slice)."""
    store = storage.get_content_store()
    store[marker_id] = content
    storage.save_content_store(store)
    return store[marker_id]

