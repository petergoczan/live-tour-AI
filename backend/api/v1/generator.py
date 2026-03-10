"""
AI fact generation via Ollama (llama3). Batch generation with retry for valid JSON.
"""
import asyncio
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from ollama import AsyncClient
from pydantic import BaseModel

from core import storage
from core.schemas import GeneratedFactList, JobStatus

router = APIRouter()
OLLAMA_MODEL = "llama3"
MAX_RETRIES = 3

PROMPT_TEMPLATE = (
    "Return exactly 5 short, interesting facts as a JSON list about the following creature: {name}. "
    "Additional context (Latin/origin name): {origin_name}. Persona: {persona}, Language: {lang}. "
    "Output only the JSON array, no other text, e.g. [\"fact1\", \"fact2\", \"fact3\", \"fact4\", \"fact5\"]."
)


def _parse_fact_list(raw: str) -> GeneratedFactList | None:
    """
    Extract a list of exactly 5 strings from model output.
    Handles markdown code blocks and strips surrounding text.
    Returns None if no valid 5-element JSON array is found.
    """
    raw = raw.strip()
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            raw = match.group(1).strip()
    start = raw.find("[")
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        arr = json.loads(raw[start:end])
        if not isinstance(arr, list) or len(arr) != 5:
            return None
        return [str(x).strip() for x in arr]
    except (json.JSONDecodeError, TypeError):
        return None


def _display_name_for_lang(marker: dict, lang: str) -> str:
    """
    Pick the creature name for the requested language: name_hu for HU, name_en for EN.
    Falls back to the other name or origin_name if the preferred one is empty.
    """
    name_hu = (marker.get("name_hu") or "").strip()
    name_en = (marker.get("name_en") or "").strip()
    origin = (marker.get("origin_name") or "").strip()
    if lang.upper() == "HU":
        return name_hu or name_en or origin or "Unknown"
    return name_en or name_hu or origin or "Unknown"


def _origin_name(marker: dict) -> str:
    """Return origin/Latin name for extra context in the prompt."""
    return (marker.get("origin_name") or "").strip() or "(none)"


async def _generate_facts_for_combo(
    name: str,
    origin_name: str,
    persona: str,
    lang: str,
) -> tuple[GeneratedFactList, bool]:
    """
    Call Ollama once per (name, persona, lang) to get 5 facts. Retries up to MAX_RETRIES on failure or invalid JSON.
    Returns (facts_list, success). success is False when fallback placeholder list is returned.
    """
    client = AsyncClient()
    prompt = PROMPT_TEMPLATE.format(
        name=name,
        origin_name=origin_name,
        persona=persona,
        lang=lang,
    )
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            content = (response.get("message") or {}).get("content") or ""
            facts = _parse_fact_list(content)
            if facts:
                return facts, True
        except Exception as e:
            last_error = e
            print(f"[generator] Attempt {attempt + 1}/{MAX_RETRIES} failed for name={name!r}, persona={persona}, lang={lang}: {e}")
        await asyncio.sleep(0.5 * (attempt + 1))

    print(f"[generator] ERROR: failed after {MAX_RETRIES} attempts (name={name!r}, persona={persona}, lang={lang}).")
    if last_error:
        print(f"[generator] Details: {type(last_error).__name__}: {last_error}")
    return [
        f"[Generation failed – {name}, {persona}, {lang}]",
        "",
        "",
        "",
        "",
    ], False


async def _run_batch_job(job_id: str, markers: list[dict], personas: list[str], languages: list[str]) -> None:
    """
    Run batch generation for all marker × persona × language combinations.
    Updates per-marker status to GENERATING then DONE or FAILED; persists results to content store.
    """
    print(f"[generator] Batch job started: job_id={job_id}, markers={len(markers)}, personas={personas}, languages={languages}")
    store = storage.get_content_store()
    for m in markers:
        marker_id = m.get("id", "")
        storage.set_marker_status(job_id, marker_id, JobStatus.GENERATING.value)
        if marker_id not in store:
            store[marker_id] = {}
        marker_failed = False
        for persona in personas:
            if persona not in store[marker_id]:
                store[marker_id][persona] = {}
            for lang in languages:
                name = _display_name_for_lang(m, lang)
                origin = _origin_name(m)
                print(f"[generator] Generating facts: marker_id={marker_id}, persona={persona}, lang={lang}, name={name!r}")
                facts, success = await _generate_facts_for_combo(name, origin, persona, lang)
                store[marker_id][persona][lang] = facts
                if not success:
                    marker_failed = True
        status = JobStatus.FAILED.value if marker_failed else JobStatus.DONE.value
        storage.set_marker_status(job_id, marker_id, status)
        print(f"[generator] Marker {status}: marker_id={marker_id}")
    storage.save_content_store(store)
    print(f"[generator] Batch job finished: job_id={job_id}")


class BatchRequest(BaseModel):
    markers: list[dict[str, Any]]
    personas: list[str]
    languages: list[str]


class BatchResponse(BaseModel):
    job_id: str


@router.post("/batch", response_model=BatchResponse)
def start_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """Start async batch generation. Poll GET /generator/status?job_id=... for per-marker status."""
    job_id = str(uuid.uuid4())
    status = {m.get("id", ""): JobStatus.PENDING.value for m in request.markers}
    storage.set_batch_job_status(job_id, status)
    background_tasks.add_task(
        _run_batch_job,
        job_id,
        request.markers,
        request.personas,
        request.languages,
    )
    print(f"[generator] Batch started: job_id={job_id}")
    return BatchResponse(job_id=job_id)


@router.get("/status")
def get_status(job_id: str):
    """Returns { marker_id: JobStatus value (pending|generating|done|failed), ... }."""
    status = storage.get_batch_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status
