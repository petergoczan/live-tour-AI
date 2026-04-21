# Live Tour AI

Live Tour AI is a FastAPI-based backend for location-aware, AI-assisted tour experiences.
It combines:

- a **mobile-facing runtime API** (`/api/v1/checkin`) for proximity check-ins and fact delivery,
- an **admin CMS UI** (`/admin`) for managing partners and markers,
- an **AI generation API** (`/api/v1/generator`) for generating marker facts with Ollama.

## What The Project Does

At a high level:

1. Admin users create **partners** and their **markers** (points of interest) in the CMS.
2. The system generates persona/language-specific facts for markers via AI.
3. Mobile clients call the check-in endpoint with GPS coordinates.
4. If the user is near a marker, the backend returns:
   - the next available fact, and
   - a short contextual wrapper sentence.

## Core Features

- **Partner-based content management**
  - Partners are stored in `backend/data/partners.json`.
  - Marker data is partitioned by partner for scalability: `backend/data/markers_{partner_id}.json`.
- **Marker validation**
  - At least one name is required (`name_hu`, `name_en`, or `origin_name`).
  - Duplicate name/position checks with clear validation errors.
- **Fact generation pipeline**
  - Batch generation endpoint using Ollama (`llama3`) with retries.
  - Status polling per marker (`pending`, `generating`, `done`, `failed`).
- **Runtime check-in flow**
  - Nearest-marker detection based on GPS distance.
  - Per-user/per-marker fact progression.
  - Wrapper sentence generation and cooldown handling.

## Tech Stack

- **Backend:** FastAPI, Pydantic
- **Templating/UI:** Jinja2 + Bootstrap 5
- **AI:** Ollama (`llama3`)
- **Server:** Uvicorn
- **Tests:** Pytest
- **Storage:** JSON files (lightweight, file-based persistence)

## Project Structure

```text
backend/
  main.py                    # FastAPI app wiring and router mounting
  api/v1/
    checkin.py               # Mobile API runtime check-in endpoints
    generator.py             # AI batch generation and status endpoints
  cms/
    routes.py                # CMS UI routes + CMS content/config endpoints
    templates/               # Admin dashboard and partner detail templates
  core/
    schemas.py               # Shared Pydantic schemas
    storage.py               # JSON file storage + cache helpers
    utils.py                 # Shared utility functions (e.g., distance calc)
  data/                      # Runtime data files (partners, markers, content)
  static/
    index.html               # Root welcome page
```

## Getting Started

### 1) Install dependencies

From `backend/`:

```bash
pip install -r requirements.txt
```

### 2) Run the server

```bash
uvicorn main:app --reload
```

Default URL: `http://127.0.0.1:8000`

## Main Routes

- `GET /`  
  Welcome page ("Welcome to Live Tour AI").

- `GET /admin`  
  CMS dashboard (partner list, add partner).

- `GET /admin/partner/{partner_id}`  
  Partner detail page (marker management + fact generation controls).

- `POST /api/v1/checkin/nearby`  
  Mobile runtime check-in endpoint.

- `POST /api/v1/generator/batch`  
  Start AI fact generation batch.

- `GET /api/v1/generator/status?job_id=...`  
  Poll generation status.

- `GET /health`  
  Health check endpoint.

## Development Notes

- Router prefixes are centralized in `backend/main.py`.
- CMS routes are consolidated in `backend/cms/routes.py` (hybrid monolith approach).
- Marker ownership is determined by storage partition file name, not marker payload.
- For local development, JSON storage keeps setup simple and transparent.

## Roadmap Ideas

- Add authentication/authorization for admin routes.
- Add database backend (PostgreSQL) for production-scale persistence.
- Add background worker queue for generation jobs.
- Add automated API/integration tests for CMS flows.

## License

Add your preferred license (e.g., MIT) to clarify usage for public contributors.