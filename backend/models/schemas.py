from pydantic import BaseModel


class LocationBase(BaseModel):
    lat: float
    lon: float
    user_id: str
