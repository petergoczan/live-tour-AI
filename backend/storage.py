"""
Simple JSON file storage for markers, global config, and content store.
ContentStore type: dict[marker_id, dict[persona, dict[lang, list[str]]]]
Job status values are JobStatus enum values (pending, generating, done, failed).
"""
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent / "data"
MARKERS_FILE = DATA_DIR / "markers.json"
CONFIG_FILE = DATA_DIR / "global_config.json"
CONTENT_FILE = DATA_DIR / "content_store.json"

# In-memory cache and batch job status: job_id -> { marker_id: status_str }
_batch_job_status: dict[str, dict[str, str]] = {}
_content_store_cache: dict | None = None
_markers_cache: list[dict] | None = None
_config_cache: dict | None = None


def _ensure_data_dir() -> None:
    """Create data directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_markers() -> list[dict]:
    """Load and return the list of markers from disk (cached)."""
    global _markers_cache
    _ensure_data_dir()
    if not MARKERS_FILE.exists():
        return []
    if _markers_cache is None:
        with open(MARKERS_FILE, encoding="utf-8") as f:
            _markers_cache = json.load(f)
    return _markers_cache


def save_markers(markers: list[dict]) -> None:
    """Persist the marker list to disk and update cache."""
    global _markers_cache
    _ensure_data_dir()
    with open(MARKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(markers, f, ensure_ascii=False, indent=2)
    _markers_cache = markers


def get_global_config() -> dict:
    """Load and return global config (personas, languages) from disk (cached)."""
    global _config_cache
    _ensure_data_dir()
    if not CONFIG_FILE.exists():
        return {"personas": ["Gyerek", "Szakértő", "Komikus"], "languages": ["HU", "EN"]}
    if _config_cache is None:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            _config_cache = json.load(f)
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
    global _content_store_cache, _markers_cache, _config_cache
    _content_store_cache = None
    _markers_cache = None
    _config_cache = None
