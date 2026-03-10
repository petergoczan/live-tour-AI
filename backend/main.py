from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from cms.routes import router as admin_router
from api.v1.checkin import router as checkin_router
from api.v1.generator import router as generator_router

app = FastAPI(title="Live Tour AI")

STATIC_DIR = Path(__file__).resolve().parent / "static"


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(admin_router, prefix="/admin", tags=["CMS UI"])
app.include_router(checkin_router, prefix="/api/v1/checkin", tags=["Mobile API"])
app.include_router(generator_router, prefix="/api/v1/generator", tags=["AI Generator"])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")
