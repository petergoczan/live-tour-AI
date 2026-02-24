from fastapi import APIRouter

from models.schemas import LocationBase

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/checkin")
def checkin(location: LocationBase):
    return {"status": "ok", "user_id": location.user_id, "lat": location.lat, "lon": location.lon}
