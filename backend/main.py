from fastapi import FastAPI

from api.v1.locations import router as locations_router

app = FastAPI(title="Live Tour AI")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(locations_router, prefix="/api/v1")
