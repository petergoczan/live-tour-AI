"""
Runtime checkin: next fact from ContentStore, optional AI wrapper sentence (background).
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from ollama import AsyncClient

import storage
from models.schemas import CheckinRequest

router = APIRouter(prefix="/checkin", tags=["checkin"])
OLLAMA_MODEL = "llama3"

# user_id -> marker_id -> fact_index (for "next fact" per user per marker)
_user_fact_index: dict[str, dict[str, int]] = {}


def _get_next_fact(user_id: str, marker_id: str, persona: str, lang: str) -> tuple[Optional[str], str]:
    """
    Return the next fact for (user_id, marker_id, persona, lang) from ContentStore and advance the index.
    Returns (fact_text, marker_name); marker_name is unused but kept for API compatibility.
    """
    store = storage.get_content_store()
    if marker_id not in store or persona not in store[marker_id] or lang not in store[marker_id][persona]:
        return None, ""
    facts = store[marker_id][persona][lang]
    if not facts:
        return None, ""
    if user_id not in _user_fact_index:
        _user_fact_index[user_id] = {}
    if marker_id not in _user_fact_index[user_id]:
        _user_fact_index[user_id][marker_id] = 0

    idx = _user_fact_index[user_id][marker_id]
    if idx >= len(facts):
        return None, ""

    fact = facts[idx]
    _user_fact_index[user_id][marker_id] += 1
    return fact, ""


def _display_name_for_wrapper(marker: dict, lang: str) -> str:
    """Pick a display name for the wrapper sentence based on the requested language."""
    name_hu = (marker.get("name_hu") or "").strip()
    name_en = (marker.get("name_en") or "").strip()
    origin = (marker.get("origin_name") or "").strip()
    if lang.upper() == "HU":
        return name_hu or name_en or origin or "creature"
    return name_en or name_hu or origin or "creature"


async def _generate_wrapper(name: str) -> str:
    """Generate a short context sentence via Ollama, e.g. 'Look, here is a {name} again!'."""
    try:
        client = AsyncClient()
        prompt = f"Reply with exactly one short sentence: 'Look, here is a {name} again!' Output only this sentence, nothing else."
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = (response.get("message") or {}).get("content") or ""
        return content.strip() or f"Look, here is a {name} again!"
    except Exception as e:
        print(f"[checkin] Wrapper generation failed for name={name!r}: {e}")
        return f"Look, here is a {name} again!"


def _run_wrapper_background(name: str) -> None:
    """BackgroundTasks callback: generate wrapper sentence (and optionally cache for future use)."""
    asyncio.run(_generate_wrapper(name))


@router.post("/")
def checkin(req: CheckinRequest, background_tasks: BackgroundTasks):
    """
    Return the next stored fact for this user/marker/persona/lang from ContentStore (no Ollama for facts).
    Starts a background task to generate a short wrapper sentence (e.g. 'Look, here is a {name} again!').
    """
    marker_id = req.marker_id
    if not marker_id:
        return {"fact": None, "wrapper": None, "error": "marker_id required"}
    store = storage.get_content_store()
    if marker_id not in store:
        return {"fact": None, "wrapper": None, "error": "No content for this marker"}
    persona, lang = req.persona, req.lang
    if persona not in store[marker_id] or lang not in store[marker_id][persona]:
        return {"fact": None, "wrapper": None, "error": "No content for this persona/lang"}
    fact = _get_next_fact(req.user_id, marker_id, persona, lang)[0]
    if fact is None:
        return {"fact": None, "wrapper": None, "error": "No facts"}
    markers = storage.get_markers()
    name = "creature"
    for m in markers:
        if m.get("id") == marker_id:
            name = _display_name_for_wrapper(m, lang)
            break
    background_tasks.add_task(_run_wrapper_background, name)
    return {"fact": fact, "wrapper": None}
