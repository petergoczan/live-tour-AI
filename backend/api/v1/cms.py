"""
CMS API: config, markers, content store (for review/edit).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import storage

router = APIRouter(prefix="/cms", tags=["cms"])


class GlobalConfigBody(BaseModel):
    personas: list[str]
    languages: list[str]


@router.get("/config")
def get_config():
    return storage.get_global_config()


@router.put("/config")
def put_config(body: GlobalConfigBody):
    storage.save_global_config({"personas": body.personas, "languages": body.languages})
    return storage.get_global_config()


@router.get("/markers")
def get_markers():
    return storage.get_markers()


@router.post("/markers")
def save_markers(markers: list[dict]):
    storage.save_markers(markers)
    return storage.get_markers()


@router.get("/content/{marker_id}")
def get_content(marker_id: str):
    """Return content store slice for one marker: { persona: { lang: list of 5 strings } }."""
    store = storage.get_content_store()
    if marker_id not in store:
        raise HTTPException(status_code=404, detail="Marker not found or no content")
    return store[marker_id]


@router.put("/content/{marker_id}")
def save_content(marker_id: str, content: dict):
    """Save content for one marker. Body: { persona: { lang: [str, str, str, str, str] } }."""
    store = storage.get_content_store()
    store[marker_id] = content
    storage.save_content_store(store)
    return store[marker_id]
