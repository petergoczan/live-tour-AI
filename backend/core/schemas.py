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


class Partner(BaseModel):
    id: str
    name: str


class Marker(BaseModel):
    id: str
    lat: float
    lng: float
    name_hu: str | None = None
    name_en: str | None = None
    origin_name: str | None = None


GeneratedFactList = list[str]  # exactly 5 strings


def content_store_type():
    """Return type alias for the nested content store structure.

    ContentStore: marker_id -> persona -> lang -> GeneratedFactList
    """

    return dict[str, dict[str, dict[str, GeneratedFactList]]]


class GlobalConfig(BaseModel):
    personas: list[str] = ["Child", "Expert", "Comic"]
    languages: list[str] = ["HU", "EN"]


class CheckinRequest(BaseModel):
    """Checkin request from the mobile app.

    - partner_id is required to scope nearby lookup
    - persona/lang select which content bucket to use
    """

    user_id: str
    partner_id: str
    lat: float
    lng: float
    marker_id: Optional[str] = None
    persona: str = "Child"
    lang: str = "EN"


class CheckinResponse(BaseModel):
    fact: str | None
    wrapper: str | None
    error: str | None = None

