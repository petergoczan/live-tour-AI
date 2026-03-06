from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    """Status of a marker within a batch generation job."""
    PENDING = "pending"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"


# --- CMS & Content ---

class Marker(BaseModel):
    id: str
    lat: float
    lng: float
    name_hu: str | None = None
    name_en: str | None = None
    origin_name: str | None = None


GeneratedFactList = list[str]  # exactly 5 strings


# ContentStore: marker_id -> persona -> lang -> GeneratedFactList
# Type alias for the nested structure (Pydantic can validate dicts)
def content_store_type():
    return dict[str, dict[str, dict[str, GeneratedFactList]]]


class GlobalConfig(BaseModel):
    personas: list[str] = ["Child", "Expert", "Comic"]
    languages: list[str] = ["HU", "EN"]


# Checkin request: may include persona/lang for content selection
class CheckinRequest(BaseModel):
    user_id: str
    lat: float
    lng: float
    marker_id: Optional[str] = None
    persona: str = "Child"
    lang: str = "EN"


class CheckinResponse(BaseModel):
    fact: str | None
    wrapper: str | None
    error: str | None = None
