"""
Simple JSON file storage for partners, markers, global config, and content store.

ContentStore type: dict[marker_id, dict[persona, dict[lang, list[str]]]]
Job status values are JobStatus enum values (pending, generating, done, failed).
"""
from pathlib import Path
import json
from typing import Iterable

from core.schemas import Marker, Partner


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PARTNERS_FILE = DATA_DIR / "partners.json"
CONFIG_FILE = DATA_DIR / "global_config.json"
CONTENT_FILE = DATA_DIR / "content_store.json"

# markers are stored partitioned by partner: markers_{partner_id}.json
MARKERS_PREFIX = "markers_"
MARKERS_SUFFIX = ".json"


# In-memory cache and batch job status: job_id -> { marker_id: status_str }
_batch_job_status: dict[str, dict[str, str]] = {}
_content_store_cache: dict | None = None
_partners_cache: list[Partner] | None = None
_config_cache: dict | None = None


def _ensure_data_dir() -> None:
    """Create data directory if it does not exist."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _markers_file_for_partner(partner_id: str) -> Path:
    """Return the JSON file path for a partner's markers."""

    return DATA_DIR / f"{MARKERS_PREFIX}{partner_id}{MARKERS_SUFFIX}"


def _iter_marker_files() -> list[Path]:
    """Return all marker partition files."""

    _ensure_data_dir()
    return list(DATA_DIR.glob(f"{MARKERS_PREFIX}*{MARKERS_SUFFIX}"))


def get_partners() -> list[Partner]:
    """Load and return the list of partners from disk (cached)."""

    global _partners_cache
    _ensure_data_dir()
    if not PARTNERS_FILE.exists():
        return []
    if _partners_cache is None:
        with open(PARTNERS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _partners_cache = [Partner(**p) for p in raw]
    if _partners_cache is None:
        return []
    return _partners_cache


def save_partner(partner: Partner) -> None:
    """Add or update a partner and persist."""

    global _partners_cache
    _ensure_data_dir()
    partners = get_partners()
    existing = next((i for i, p in enumerate(partners) if p.id == partner.id), None)
    if existing is not None:
        partners[existing] = partner
    else:
        partners.append(partner)
    with open(PARTNERS_FILE, "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in partners], f, ensure_ascii=False, indent=2)
    _partners_cache = partners


def get_markers_by_partner(partner_id: str) -> list[Marker]:
    """Return markers that belong to the given partner.

    Loads from the dedicated markers_{partner_id}.json file.
    """

    _ensure_data_dir()
    path = _markers_file_for_partner(partner_id)
    if not path.exists():
        print(
            f"[storage] Returning empty marker list: no marker data found for partner_id={partner_id!r} "
            f"(expected file: {path})"
        )
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [Marker(**m) for m in raw]


def save_markers_for_partner(partner_id: str, markers: list[Marker]) -> None:
    """Replace all markers for a partner with the given list."""

    _ensure_data_dir()
    serializable = [m.model_dump() for m in markers]
    path = _markers_file_for_partner(partner_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def save_marker(partner_id: str, marker: Marker) -> None:
    """Add or update a single marker for a partner."""

    markers = get_markers_by_partner(partner_id)
    updated: list[Marker] = []
    found = False
    for m in markers:
        if m.id == marker.id:
            updated.append(marker)
            found = True
        else:
            updated.append(m)
    if not found:
        updated.append(marker)
    save_markers_for_partner(partner_id, updated)


def get_global_config() -> dict:
    """Load and return global config (personas, languages) from disk (cached)."""

    global _config_cache
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        return {"personas": ["Child", "Expert", "Comedian"], "languages": ["HU", "EN"]}
    if _config_cache is None:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            _config_cache = json.load(f)
    if _config_cache is None:
        # Fallback for static type checkers: guarantee a dict return type.
        return {"personas": ["Child", "Expert", "Comedian"], "languages": ["HU", "EN"]}
    return _config_cache


def save_global_config(config: dict) -> None:
    """Persist global config to disk and update cache."""

    global _config_cache
    _ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    _config_cache = config


def get_content_store() -> dict:
    """Return ContentStore: dict[marker_id, dict[persona, dict[lang, list[str]]]] (cached)."""

    global _content_store_cache
    _ensure_data_dir()
    if not CONTENT_FILE.exists():
        return {}
    if _content_store_cache is None:
        with open(CONTENT_FILE, encoding="utf-8") as f:
            _content_store_cache = json.load(f)
    if _content_store_cache is None:
        # Fallback for static type checkers: guarantee a dict return type.
        return {}
    return _content_store_cache


def save_content_store(store: dict) -> None:
    """Persist content store to disk and update cache."""

    global _content_store_cache
    _ensure_data_dir()
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    _content_store_cache = store


def get_batch_job_status(job_id: str) -> dict[str, str] | None:
    """Return per-marker status for a batch job (status values: pending, generating, done, failed)."""

    return _batch_job_status.get(job_id)


def set_batch_job_status(job_id: str, status: dict[str, str]) -> None:
    """Set the full status map for a batch job."""

    _batch_job_status[job_id] = status


def set_marker_status(job_id: str, marker_id: str, status: str) -> None:
    """Update status of a single marker within a batch job."""

    if job_id not in _batch_job_status:
        _batch_job_status[job_id] = {}
    _batch_job_status[job_id][marker_id] = status


def invalidate_caches() -> None:
    """Clear in-memory caches (e.g. for tests)."""

    global _content_store_cache, _partners_cache, _config_cache
    _content_store_cache = None
    _partners_cache = None
    _config_cache = None

