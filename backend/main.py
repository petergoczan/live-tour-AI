from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.v1.generator import router as generator_router
from api.v1.checkin import router as checkin_router
from api.v1.cms import router as cms_router

app = FastAPI(title="Live Tour AI")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(generator_router, prefix="/api/v1")
app.include_router(checkin_router, prefix="/api/v1")
app.include_router(cms_router, prefix="/api/v1")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")
