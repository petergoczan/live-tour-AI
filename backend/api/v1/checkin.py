"""
Runtime checkin: next fact from ContentStore and AI wrapper sentence.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from ollama import AsyncClient

import storage
from models.schemas import CheckinRequest, CheckinResponse
from utils import calculate_distance

router = APIRouter(prefix="/checkin", tags=["checkin"])
OLLAMA_MODEL = "llama3"

# Shared Ollama client for this module to avoid creating a new client per request.
_ollama_client = AsyncClient()

# user_id -> marker_id -> fact_index (for "next fact" per user per marker)
_user_fact_index: dict[str, dict[str, int]] = {}

# user_id -> marker_id -> last checkin timestamp (used to know if user has ever visited a marker)
_user_last_seen: dict[str, dict[str, datetime]] = {}

# user_id -> last marker_id with a successful fact response
_user_last_marker: dict[str, str] = {}


class WrapperMode(str, Enum):
    FIRST = "FIRST"
    AGAIN = "AGAIN"
    STILL = "STILL"


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
        # Already past the last fact: do not loop back to the beginning.
        return None, ""

    fact = facts[idx]
    _user_fact_index[user_id][marker_id] += 1
    return fact, ""


def _display_name_for_wrapper(marker: dict, lang: str) -> Optional[str]:
    """Pick a display name for the wrapper sentence based on the requested language.

    Returns None when no suitable name is available; the wrapper generator will then
    use a generic language-specific fallback sentence (e.g. 'Itt van valami.').
    """
    name_hu = (marker.get("name_hu") or "").strip()
    name_en = (marker.get("name_en") or "").strip()
    origin = (marker.get("origin_name") or "").strip()
    if lang.upper() == "HU":
        name = name_hu or name_en or origin
    else:
        name = name_en or origin
    return name or None


async def _generate_wrapper(name: Optional[str], mode: WrapperMode, lang: str) -> str:
    """Generate a short context sentence via Ollama based on the wrapper mode and language."""
    if lang.upper() == "HU":
        if name:
            if mode == WrapperMode.FIRST:
                core_sentence = f"Nézd, itt egy {name}!"
            elif mode == WrapperMode.AGAIN:
                core_sentence = f"Nézd, itt van újra egy {name}!"
            else:
                core_sentence = f"Látom, még mindig egy {name} előtt vagy!"
        else:
            # No display name available: use a generic Hungarian fallback.
            core_sentence = "Itt van valami."
        language_label = "Hungarian"
    else:
        if name:
            if mode == WrapperMode.FIRST:
                core_sentence = f"Look, here is a {name}!"
            elif mode == WrapperMode.AGAIN:
                core_sentence = f"Look, here is the {name} again!"
            else:
                core_sentence = f"I see you are still in front of the {name}!"
        else:
            # No display name available: use a generic English fallback.
            core_sentence = "Here is something."
        language_label = "English"

    try:
        client = _ollama_client
        prompt = (
            f"Reply with exactly one short {language_label} sentence: "
            f"'{core_sentence}' Output only this sentence, nothing else."
        )
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = (response.get("message") or {}).get("content") or ""
        return content.strip() or core_sentence
    except Exception as e:
        print(f"[checkin] Wrapper generation failed for name={name!r}, mode={mode}, lang={lang}: {e}")
        return core_sentence


async def do_checkin(req: CheckinRequest) -> CheckinResponse:
    """Core checkin logic: get next fact and wrapper for a specific marker."""
    marker_id = req.marker_id
    if not marker_id:
        return CheckinResponse(fact=None, wrapper=None, error="marker_id required")
    store = storage.get_content_store()
    if marker_id not in store:
        return CheckinResponse(fact=None, wrapper=None, error="No content for this marker")
    persona, lang = req.persona, req.lang
    if persona not in store[marker_id] or lang not in store[marker_id][persona]:
        return CheckinResponse(fact=None, wrapper=None, error="No content for this persona/lang")

    # Determine wrapper mode before fetching the next fact:
    # - FIRST: user has never checked in to this marker before.
    # - AGAIN: user has been here before and between visits has successfully checked in to at least one other marker.
    # - STILL: user has been here before and has not successfully checked in to any other marker in between.
    #   STILL is only allowed if at least 2 minutes have passed since the last successful checkin for this marker;
    #   otherwise we return an error and do not advance the fact index.
    now = datetime.now()
    user_seen = _user_last_seen.get(req.user_id)
    if user_seen is None or marker_id not in user_seen:
        mode = WrapperMode.FIRST
    else:
        last_marker = _user_last_marker.get(req.user_id)
        if last_marker is not None and last_marker != marker_id:
            mode = WrapperMode.AGAIN
        else:
            # Candidate STILL: enforce minimum time window for a new fact on the same marker.
            last_seen = user_seen[marker_id]
            if now - last_seen < timedelta(minutes=2):
                return CheckinResponse(
                    fact=None,
                    wrapper=None,
                    error="Not enough time has passed for a new fact",
                )
            mode = WrapperMode.STILL

    fact = _get_next_fact(req.user_id, marker_id, persona, lang)[0]
    if fact is None:
        # No more facts available for this marker/persona/lang combination.
        # Return success with fact=None so the client can stay silent.
        return CheckinResponse(fact=None, wrapper=None, error=None)

    # Successful fact delivery: update last-seen markers for future mode decisions.
    if user_seen is None:
        _user_last_seen[req.user_id] = {}
    _user_last_seen[req.user_id][marker_id] = now
    _user_last_marker[req.user_id] = marker_id

    markers = storage.get_markers()
    name: Optional[str] = None
    for m in markers:
        if m.get("id") == marker_id:
            name = _display_name_for_wrapper(m, lang)
            break

    wrapper = await _generate_wrapper(name, mode, lang)
    return CheckinResponse(fact=fact, wrapper=wrapper, error=None)


@router.post("/nearby", response_model=CheckinResponse)
async def checkin(req: CheckinRequest) -> CheckinResponse:
    """
    Receive coordinates from the mobile app and, if the user is within 15 meters of a marker,
    delegate to the main checkin flow for that marker.
    """
    if req.lat is None or req.lon is None:
        return CheckinResponse(fact=None, wrapper=None, error="GPS coordinates required")

    markers = storage.get_markers()
    target_marker_id: str | None = None
    closest_distance: float | None = None

    # Find the closest marker within 15 meters of the user's location.
    for m in markers:
        dist = calculate_distance(req.lat, req.lon, m["lat"], m["lng"])
        if dist <= 15 and (closest_distance is None or dist < closest_distance):
            target_marker_id = m["id"]
            closest_distance = dist

    if not target_marker_id:
        return CheckinResponse(fact=None, wrapper=None, error="no_marker_nearby")

    # If we found a nearby marker, reuse the existing core checkin logic.
    req.marker_id = target_marker_id
    return await do_checkin(req)
