# DataForge — FastAPI Project Folder Structure Plan

**Task:** M1W2T13 — FastAPI Project Folder Structure Plan
**Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)
**Milestone:** 1 · Week 2 · 18–24 May 2026
**Output path:** `/docs/api/fastapi_project_structure.md`
**Status:** Draft v1 — pending Abdullah review (M1W2T6)
**Goal:** Lock the FastAPI backend layout **before any code is written** to prevent structural rework in M9.
**Aligned with:** T10 (`api_endpoints_v1.md`), T11 (`db_table_sketches.md`), T12 (`api_dashboard_traceability.md`)

---

## 1. Purpose

FastAPI is intentionally unopinionated about project layout — a small example fits in one file, but the DataForge backend will host **18 endpoints** consuming **7 TimescaleDB tables** and **5 continuous aggregates**, with a clear distinction between persistence, business logic, and wire-format concerns.

This document fixes the project layout up-front to guarantee:

- **No structural rework in M9** — the layer boundaries are set now, before code lands.
- **Predictable module boundaries** — a new contributor can find any endpoint in under 30 seconds.
- **Testable layers** — services are isolated from HTTP and from each other; tests live in symmetric directories.
- **Clean migration story** — Alembic owns schema, application owns runtime.

The structure draws on established FastAPI community patterns (the "domain-driven" or "Netflix Dispatch" layout) adapted to our specific needs (TimescaleDB hypertables, WebSocket bridge, PDF export, JWT post-M9).

---

## 2. Top-Level Repository Context

The FastAPI backend lives under `/api/` inside the DataForge monorepo. Surrounding directories (for context, not detailed here):

```
/dataforge/                            (repo root)
├── README.md
├── docker-compose.yml                  Local stack (Kafka, TimescaleDB, FastAPI, frontend)
├── .env.example
│
├── docs/                               Documentation
│   ├── api/                            T10, T12, T13 (this doc)
│   ├── database/                       T11
│   ├── data/                           T17 (CERN exploration)
│   └── architecture/                   Abdullah's diagrams
│
├── dashboard/                          ReactJS frontend
│   ├── specs/                          T9
│   ├── wireframes/                     T14, T15
│   └── src/
│
├── api/                                ←  THIS DOCUMENT'S SCOPE  (FastAPI backend)
│
├── pipeline/                           M3-M6 (Abdullah + Omer)
│   ├── adaptation/                     Module 3
│   ├── cleaning/                       Module 5
│   └── fusion/                         Module 6
│
├── ml/                                 M7-M8 (Abdullah)
│   ├── anomaly_detection/              Module 7
│   └── xai/                            Module 8
│
├── infrastructure/
│   └── kafka/                          docker-compose for Kafka (KRaft)
│
└── tests/                              Cross-module integration tests (M10)
```

---

## 3. FastAPI Backend Tree (the `/api/` directory)

```
api/
├── README.md
├── pyproject.toml                      Dependency declarations (Poetry or pip-tools)
├── alembic.ini                         Alembic config (DB migrations)
├── .env.example                        Template — never committed with real secrets
├── Dockerfile                          Production container image
├── docker-compose.override.yml         Optional dev overrides
│
├── app/
│   ├── __init__.py
│   ├── main.py                         FastAPI app entrypoint; mounts routers
│   ├── config.py                       Pydantic Settings — env-driven configuration
│   ├── dependencies.py                 FastAPI Depends() factories (DB session, services)
│   │
│   ├── routers/                        ← BRIEF FOLDER 1
│   │   ├── __init__.py
│   │   ├── summary.py                  GET /api/v1/summary
│   │   ├── alerts.py                   GET/PATCH /api/v1/alerts/*
│   │   ├── fusion.py                   GET /api/v1/fusion/*
│   │   ├── performance.py              GET /api/v1/performance/*
│   │   ├── reports.py                  GET /api/v1/reports/*
│   │   ├── stream.py                   GET /api/v1/stream/info
│   │   ├── health.py                   GET /api/v1/health and /health/upstream
│   │   └── ws.py                       WebSocket: /ws/stream, /ws/fusion
│   │
│   ├── models/                         ← BRIEF FOLDER 2 (SQLAlchemy ORM)
│   │   ├── __init__.py
│   │   ├── base.py                     Declarative base + naming convention
│   │   ├── events.py                   `events` table
│   │   ├── clean_events.py             `clean_events`
│   │   ├── fused_events.py             `fused_events`
│   │   ├── anomaly_alerts.py           `anomaly_alerts`
│   │   ├── xai_explanations.py         `xai_explanations`
│   │   ├── system_performance_metrics.py
│   │   └── alert_status_log.py
│   │
│   ├── schemas/                        ← BRIEF FOLDER 3 (Pydantic DTOs)
│   │   ├── __init__.py
│   │   ├── common.py                   Pagination, error responses, enums
│   │   ├── summary.py                  /summary response shape
│   │   ├── alerts.py                   Alert list + detail + PATCH request
│   │   ├── fusion.py                   Sensors list + drill-down
│   │   ├── performance.py              Time-series response + thresholds
│   │   ├── reports.py                  Aggregated report payload
│   │   ├── xai.py                      SHAP response (summary + full)
│   │   └── ws.py                       WebSocket message schemas
│   │
│   ├── services/                       ← BRIEF FOLDER 4 (Business logic)
│   │   ├── __init__.py
│   │   ├── summary_service.py          Aggregations for /summary
│   │   ├── alerts_service.py           Filtering, status updates, PATCH lifecycle
│   │   ├── fusion_service.py           Sensor health computation
│   │   ├── performance_service.py      KPI time-series queries against CAGGs
│   │   ├── reports_service.py          Multi-table aggregation
│   │   ├── exporter_service.py         PDF (ReportLab) / CSV export
│   │   ├── xai_service.py              SHAP retrieval + format negotiation
│   │   └── kafka_bridge.py             WebSocket ↔ Kafka consumer bridge
│   │
│   ├── db/                             ← BRIEF FOLDER 5 (TimescaleDB)
│   │   ├── __init__.py
│   │   ├── session.py                  asyncpg pool, AsyncSession factory
│   │   ├── connection.py               Connection string assembly, retry policy
│   │   ├── continuous_aggregates.py    CAGG materialization helpers (read-only)
│   │   └── migrations/                 Alembic
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/
│   │           ├── 001_initial_schema.py        Create 7 tables
│   │           ├── 002_hypertables.py           create_hypertable() calls
│   │           ├── 003_indexes.py
│   │           ├── 004_compression_policies.py
│   │           ├── 005_retention_policies.py
│   │           └── 006_continuous_aggregates.py 5 CAGGs from T11
│   │
│   ├── core/                           Cross-cutting concerns (recommended addition)
│   │   ├── __init__.py
│   │   ├── logging.py                  Structured logging (JSON + request-id)
│   │   ├── errors.py                   RFC 7807 problem detail handlers
│   │   ├── security.py                 JWT verification (active from M9 onward)
│   │   ├── middleware.py               CORS, request-id, timing
│   │   └── pagination.py               OFFSET-LIMIT helper used by routers
│   │
│   └── utils/                          Tiny stateless helpers (recommended addition)
│       ├── __init__.py
│       └── time.py                     timestamp_ms ↔ datetime conversion
│
├── tests/                              ← BRIEF FOLDER 6
│   ├── __init__.py
│   ├── conftest.py                     pytest fixtures (test DB, app, client)
│   ├── unit/                           No DB — pure logic
│   │   ├── test_services_alerts.py
│   │   ├── test_services_summary.py
│   │   └── test_pagination.py
│   ├── integration/                    With test DB (testcontainers or compose)
│   │   ├── test_routers_summary.py
│   │   ├── test_routers_alerts.py
│   │   ├── test_routers_fusion.py
│   │   ├── test_routers_performance.py
│   │   ├── test_routers_reports.py
│   │   └── test_ws_stream.py
│   └── fixtures/
│       └── seed_events.sql             Curated anomalous-event seed for tests
│
└── scripts/                            One-off operational helpers (recommended)
    ├── seed_demo_data.py               Inserts ~10K fake events for local UI demo
    └── generate_load.py                Load generator for M10 latency tests
```

**Folder count:**

- **6 brief-required:** `routers/`, `models/`, `schemas/`, `services/`, `db/`, `tests/`
- **3 recommended extras:** `core/`, `utils/`, `scripts/`

---

## 4. Per-Folder Rationale (the "why")

### 4.1 `routers/` — one file per endpoint family

**What goes in it:** Thin HTTP plumbing — path declaration, query/path/body parameter parsing, response model wiring, call into a service. **No business logic.** Average file length stays under ~150 lines.

**Why split this way:**

- Each of T10's 7 endpoint families maps to one router file (`summary.py`, `alerts.py`, `fusion.py`, …). Anyone reading the code finds the GET `/api/v1/alerts/recent` handler in `routers/alerts.py` in seconds.
- Independent inclusion in `main.py`: `app.include_router(alerts.router, prefix="/api/v1/alerts")`. Adding or removing endpoint families doesn't touch unrelated code.
- WebSocket endpoints live in `ws.py` separately because their lifecycle (connect/disconnect/heartbeat) differs significantly from REST.
- Health checks live in `health.py` because they have different semantics (no auth, no DB writes, must respond fast even when other services are degraded).

**Anti-pattern avoided:** A single `endpoints.py` of 1 200 lines mixing all 18 endpoints — common in tutorials but unmaintainable at any real scale.

### 4.2 `models/` — SQLAlchemy ORM only (persistence layer)

**What goes in it:** SQLAlchemy declarative models that mirror the 7 tables from T11. **Nothing else** — no JSON serialization, no business methods, no validators. One file per table.

**Why split from `schemas/`:**

- Models describe **what the database looks like**. Schemas describe **what the API JSON looks like**. These two things will diverge over time (a column might be renamed in DB without breaking the API; an API field might combine two DB columns).
- Decoupling lets DB migrations move independently of API versioning.
- Models reference `app.models.base.Base` (declarative base with naming convention for constraints — important for Alembic autogenerate to produce clean migration names).

**Convention:** Column name = field name from T11 spec verbatim. Composite primary keys (e.g. `(event_id, timestamp_ms)`) declared with `primary_key=True` on each member.

### 4.3 `schemas/` — Pydantic DTOs (request + response)

**What goes in it:** Pydantic `BaseModel` subclasses for every request body and every response payload. Auto-generates OpenAPI spec at `/api/v1/docs`.

**Why a separate folder:**

- Required for FastAPI's response-validation and OpenAPI generation.
- Pydantic enforces validation at the boundary — invalid client requests fail with a 422 before reaching `services/`.
- Allows API-versioning without DB changes: `schemas/v1/` could one day live next to `schemas/v2/` while `models/` stays single-version.
- Pydantic `Field()` constraints (e.g. `ge=0, le=1` for risk_score) document and enforce the spec from T9.

**Convention:** One file per endpoint family, matching `routers/`. Shared types (Pagination, ErrorResponse) live in `schemas/common.py`. Enum types from T9 (`source_type`, `status`, `quality_flag`) declared as `Literal[…]` for OpenAPI clarity.

### 4.4 `services/` — business logic (the "what we do" layer)

**What goes in it:** All SQL queries, aggregation logic, computed fields, business rules (e.g. "critical = risk_score > 0.7 AND status = open"), PDF generation, Kafka consumer state. **Routers call services; services call models.**

**Why separated:**

- Routers stay thin and HTTP-specific. Services are pure Python — unit-testable without spinning up FastAPI or a test client.
- A single service method can be reused by multiple routers (e.g. `AlertsService.get_recent()` is called by both `/api/v1/summary` for the Home banner and `/api/v1/alerts/recent` for the AI Alerts list).
- Easier to mock: integration tests can swap the real `AlertsService` for an in-memory fake when they want to test the router alone.

**Convention:** Class per service (`AlertsService`, `FusionService`, …) with a constructor taking an `AsyncSession`. Stateless methods. SQL composed via SQLAlchemy 2.0 `select()` expressions.

### 4.5 `db/` — connection and migration layer

**What goes in it:** The `asyncpg` engine, session factory, the dependency injector that yields a session per request, the Alembic migration tree, and helpers for managing continuous aggregates.

**Why separated:**

- Database session lifecycle (open → use → commit/rollback → close) is delicate and error-prone. Centralising it in `db/session.py` ensures every request follows the same pattern.
- Alembic migrations live under `db/migrations/` not at repo root, keeping them with the code they migrate.
- TimescaleDB-specific operations (`create_hypertable()`, `add_continuous_aggregate_policy()`) are SQL calls outside SQLAlchemy's normal scope. Wrapping them in helper functions in `db/continuous_aggregates.py` keeps the rest of the code clean.

### 4.6 `tests/` — symmetric to `app/`

**What goes in it:** pytest test files organised into `unit/` (no DB, pure logic) and `integration/` (full app + test DB), plus shared fixtures and seed SQL.

**Why split unit vs integration:**

- Unit tests run in <1 s total. Integration tests can take 30+ s for DB spin-up. Developers want both available but rarely run all integration tests on every change.
- pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`) let CI run them in parallel pipelines.
- `conftest.py` defines fixtures used by both layers: `test_db`, `app`, `client`, `auth_token`.

### 4.7 `core/` — cross-cutting concerns (recommended extra)

Not in the brief, but every non-trivial FastAPI project ends up needing these:

- `logging.py` — structured (JSON) logging with request-id propagation.
- `errors.py` — global exception handlers that emit RFC 7807 error bodies (per T10 conventions).
- `security.py` — JWT decode/verify (active from M9; stub in M1).
- `middleware.py` — CORS, request-id assignment, request timing for `/health/upstream`.
- `pagination.py` — shared OFFSET-LIMIT helper used by `alerts` and `reports` routers.

**Why not in `services/`:** these aren't business logic; they're infrastructure. Mixing them dilutes the meaning of "service".

### 4.8 `utils/` — tiny stateless helpers (recommended extra)

Stateless functions used in multiple places: `timestamp_ms_to_datetime()`, etc. Three lines apiece. Anything that grows beyond "tiny stateless helper" graduates to `core/` or `services/`.

### 4.9 `scripts/` — one-off operational helpers (recommended extra)

- `seed_demo_data.py` — for development, generate fake events so the dashboard isn't empty.
- `generate_load.py` — for M10 latency tests, push N events/sec into Kafka.

These aren't part of the running app; they're CLI tools run by hand. Separated to avoid bloating `app/`.

---

## 5. Dependency Direction Rules

A strict layering rule prevents the codebase from becoming a tangle:

```
routers/ ──→ services/ ──→ models/ ──→ db/
   ↓
schemas/
```

| Layer | May import from | May NOT import from |
|---|---|---|
| `routers/` | `services/`, `schemas/`, `dependencies.py`, `core/` | `models/` directly (use services), other routers |
| `services/` | `models/`, `db/`, `schemas/`, `core/`, `utils/` | `routers/` (services never reach back into HTTP) |
| `schemas/` | `schemas/common.py`, stdlib | `models/`, `services/`, `routers/`, `db/` |
| `models/` | `db/base.py`, SQLAlchemy | `schemas/`, `services/`, `routers/` |
| `db/` | `models/`, SQLAlchemy/asyncpg | `routers/`, `services/`, `schemas/` |
| `core/`, `utils/` | stdlib only | Anything app-specific |

**Why this matters:** Imports are dependency declarations. A `model` that imports a `schema` is a code smell — it means persistence knows about the wire format. The rule above is mechanically enforceable: a pre-commit hook can run `import-linter` to fail PRs that violate it. Worth doing in M2.

**The one exception:** `dependencies.py` and `main.py` import widely because they're the wiring layer.

---

## 6. File Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Router files | `<feature>.py` matching endpoint prefix | `alerts.py` for `/api/v1/alerts/*` |
| Model files | `<table_name>.py` matching SQL table | `anomaly_alerts.py` |
| Schema files | `<feature>.py` matching router | `alerts.py` |
| Service classes | `<Feature>Service` | `AlertsService` |
| Pydantic models | PascalCase, suffix indicates role | `Alert`, `AlertListResponse`, `StatusUpdateRequest` |
| Service methods | snake_case verbs | `get_recent()`, `update_status()` |
| SQLAlchemy columns | snake_case matching SQL | `event_id`, `risk_score` |
| Test files | `test_<target>.py` | `test_services_alerts.py`, `test_routers_alerts.py` |
| Migration files | `NNN_<verb>_<noun>.py` | `001_initial_schema.py`, `006_continuous_aggregates.py` |

---

## 7. Sample File Skeletons

### 7.1 `app/main.py`

```python
from fastapi import FastAPI
from app.config import settings
from app.routers import (
    summary, alerts, fusion, performance, reports, stream, health, ws,
)
from app.core.middleware import setup_middleware
from app.core.errors import setup_exception_handlers

app = FastAPI(
    title="DataForge API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

setup_middleware(app)
setup_exception_handlers(app)

app.include_router(summary.router,     prefix="/api/v1")
app.include_router(alerts.router,      prefix="/api/v1/alerts", tags=["alerts"])
app.include_router(fusion.router,      prefix="/api/v1/fusion", tags=["fusion"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["performance"])
app.include_router(reports.router,     prefix="/api/v1/reports", tags=["reports"])
app.include_router(stream.router,      prefix="/api/v1/stream", tags=["stream"])
app.include_router(health.router,      prefix="/api/v1/health", tags=["health"])
app.include_router(ws.router)          # WS paths defined inside the router
```

### 7.2 `app/routers/alerts.py` (illustrative — 3 of 5 endpoints shown)

```python
from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from app.schemas.alerts import (
    AlertListResponse, AlertDetailResponse, StatusUpdateRequest, SummaryResponse,
)
from app.services.alerts_service import AlertsService
from app.dependencies import get_alerts_service

router = APIRouter()

@router.get("/recent", response_model=AlertListResponse)
async def recent_alerts(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    service: AlertsService = Depends(get_alerts_service),
):
    """Returns the latest N anomaly alerts (see /api/v1/alerts/recent in T10)."""
    return await service.get_recent(limit=limit)

@router.get("/{event_id}", response_model=AlertDetailResponse)
async def get_alert(
    event_id: str,
    service: AlertsService = Depends(get_alerts_service),
):
    alert = await service.get_by_id(event_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@router.patch("/{event_id}", response_model=AlertDetailResponse)
async def update_status(
    event_id: str,
    body: StatusUpdateRequest,
    service: AlertsService = Depends(get_alerts_service),
):
    return await service.update_status(event_id, body.status)
```

### 7.3 `app/schemas/alerts.py`

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.common import Pagination

SourceType = Literal["alice", "radar", "lidar", "telemetry"]
AlertStatus = Literal["open", "reviewed", "closed"]

class Alert(BaseModel):
    event_id: str
    timestamp: datetime
    source_type: SourceType
    anomaly_label: int = Field(ge=0, le=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    status: AlertStatus

class AlertListResponse(BaseModel):
    alerts: list[Alert]
    pagination: Pagination

class StatusUpdateRequest(BaseModel):
    status: AlertStatus
```

### 7.4 `app/models/anomaly_alerts.py`

```python
from sqlalchemy import Column, String, BigInteger, Float, SmallInteger, DateTime
from app.models.base import Base

class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"

    event_id          = Column(String,       primary_key=True)
    timestamp_ms      = Column(BigInteger,   primary_key=True)
    fused_event_id    = Column(String,       nullable=False)
    source_type       = Column(String(16),   nullable=False)
    anomaly_label     = Column(SmallInteger, nullable=False)
    risk_score        = Column(Float,        nullable=False)
    confidence        = Column(Float,        nullable=False)
    model_version     = Column(String(16),   nullable=False)
    status            = Column(String(16),   nullable=False, default="open")
    status_updated_at = Column(DateTime(timezone=True))
    status_updated_by = Column(String)
    created_at        = Column(DateTime(timezone=True), nullable=False)
```

### 7.5 `app/services/alerts_service.py`

```python
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.anomaly_alerts import AnomalyAlert
from datetime import datetime, timezone

class AlertsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_recent(self, limit: int = 50) -> list[AnomalyAlert]:
        stmt = (
            select(AnomalyAlert)
            .order_by(AnomalyAlert.risk_score.desc(),
                      AnomalyAlert.timestamp_ms.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, event_id: str) -> AnomalyAlert | None:
        stmt = select(AnomalyAlert).where(AnomalyAlert.event_id == event_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_status(self, event_id: str, new_status: str) -> AnomalyAlert:
        stmt = (
            update(AnomalyAlert)
            .where(AnomalyAlert.event_id == event_id)
            .values(status=new_status, status_updated_at=datetime.now(timezone.utc))
            .returning(AnomalyAlert)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()
```

### 7.6 `app/db/session.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(
    settings.database_url,                # postgresql+asyncpg://user:pass@host/db
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False,
)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

### 7.7 `app/dependencies.py`

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.alerts_service import AlertsService
from app.services.summary_service import SummaryService

def get_alerts_service(session: AsyncSession = Depends(get_session)) -> AlertsService:
    return AlertsService(session)

def get_summary_service(session: AsyncSession = Depends(get_session)) -> SummaryService:
    return SummaryService(session)
```

### 7.8 `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str                          # required
    kafka_bootstrap_servers: str = "localhost:9092"
    cors_origins: list[str] = ["http://localhost:3000"]
    jwt_secret: str | None = None              # M9+
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATAFORGE_")

settings = Settings()
```

---

## 8. Configuration Management

- **All runtime config via environment variables.** No hard-coded values in code.
- **Pydantic `Settings`** (in `app/config.py`) loads from `.env` in development and from process env in production.
- **`.env.example` committed**, `.env` is `.gitignore`-d.
- **Prefix:** `DATAFORGE_*` to avoid clashing with other tools.

```
.env.example
─────────────
DATAFORGE_DATABASE_URL=postgresql+asyncpg://dataforge:devpass@localhost:5432/dataforge
DATAFORGE_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DATAFORGE_CORS_ORIGINS=["http://localhost:3000"]
DATAFORGE_LOG_LEVEL=INFO
# DATAFORGE_JWT_SECRET=<set in M9>
```

---

## 9. Migration Approach (Alembic)

- **Alembic owns the schema.** No `Base.metadata.create_all()` in app startup — that would create un-versioned tables.
- **`alembic.ini`** at repo root, **`app/db/migrations/`** holds versions.
- **Naming convention:** `NNN_<verb>_<noun>.py`, three-digit zero-padded for sort order.
- **Migration plan (per T11 Section 10):**

```
001_initial_schema.py            7 tables, columns, primary keys
002_hypertables.py               create_hypertable() for 5 hypertables
003_indexes.py                   Domain indexes (risk_score, source_type, etc.)
004_compression_policies.py      add_compression_policy() per table
005_retention_policies.py        add_retention_policy() per table
006_continuous_aggregates.py     5 CAGGs from T11 Section 5
007_seed_data.py                 (optional, dev/test only)
```

- **TimescaleDB-specific calls** (e.g. `create_hypertable`) are issued via raw SQL inside the migration using `op.execute(text(...))`. Alembic's autogenerate doesn't understand them.
- **Startup check:** `app/main.py` queries `alembic_version` table on boot; logs current revision and warns if `head` is newer.

---

## 10. Testing Strategy

| Test category | Lives in | Spins up | Run command |
|---|---|---|---|
| **Unit** | `tests/unit/` | Nothing (pure Python) | `pytest tests/unit/ -m unit` |
| **Integration** | `tests/integration/` | Test DB via testcontainers OR `docker-compose -f docker-compose.test.yml` | `pytest tests/integration/ -m integration` |
| **E2E (M10)** | `/tests/` repo root | Full stack (Kafka + DB + frontend) | Handled by M10, not in `api/` |

**Fixtures:**

- `conftest.py:test_db` — provisions an empty Timescale DB, applies migrations, returns a session.
- `conftest.py:client` — `httpx.AsyncClient` against the FastAPI app with test DB injected.
- `conftest.py:seed_alerts` — loads `fixtures/seed_events.sql` (~50 curated rows including known anomalies).

**Coverage target for M9:** ≥ 80% on `services/`, ≥ 60% on `routers/` (routers are mostly plumbing).

---

## 11. Open Questions for Abdullah (Wednesday review)

1. **Models vs ORMs** — SQLAlchemy 2.0 async is the assumed choice. Alternative: `databases` + raw SQL. SQLAlchemy is heavier but gives migration autogenerate. Acceptable trade-off?
2. **Alembic vs hand-rolled SQL migrations** — Alembic is the recommendation, but raw SQL files committed to `db/migrations/sql/` is simpler. Does the team prefer either?
3. **Service-per-feature vs service-per-table** — Currently service-per-feature (matches routers). Alternative: service-per-table (matches models). Service-per-feature wins on cohesion; service-per-table on reuse. Default to service-per-feature; switch if M9 shows excessive cross-service calls.
4. **Should `tests/` live under `api/` or at the monorepo root?** Currently both: `api/tests/` for API-only tests, repo root `/tests/` for cross-module integration. Acceptable?
5. **JWT vs API key for inter-service auth** — Module 7's inference service may call the dashboard API to write back risk scores. Should it use JWT (heavier) or a static API key (simpler)?
6. **WebSocket → Kafka bridge home** — Currently in `services/kafka_bridge.py`. Should it instead live in `routers/ws.py` (closer to the WS endpoint definition)? Slight preference for `services/` for testability.
7. **Module-name prefix in service files** — `alerts_service.py` vs `alerts.py`. Currently using `_service` suffix to avoid shadowing the schema/router file names. Acceptable?

---

## 12. Next Steps

1. **Wednesday 22 May EOD** — Share this plan with Abdullah for M1W2T6 review.
2. **Thursday 22 May** — Incorporate feedback into v2.
3. **Friday 23 May** — Commit `fastapi_project_structure.md` to `/docs/api/` on GitHub (M1W2T16).
4. **M2 kickoff** — Scaffold the directory tree via `cookiecutter` or by hand. No code yet — just empty files with module docstrings.
5. **M2 implementation** — First router + first service + first model end-to-end (`/api/v1/summary`). Validates the structure before all other routers follow the pattern.
6. **Pre-commit hook** — Add `import-linter` to enforce the dependency-direction rules from Section 5.

---

## 13. References

- T9 — `dashboard_data_fields.xlsx` (in `/dashboard/specs/`)
- T10 — `api_endpoints_v1.md` (in `/docs/api/`)
- T11 — `db_table_sketches.md` (in `/docs/database/`)
- T12 — `api_dashboard_traceability.md` (in `/docs/api/`)
- Abdullah's data flow spec — `data_flow_spec.md`
- FastAPI docs — [Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- SQLAlchemy 2.0 — [Async ORM Quickstart](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- Alembic — [Async migrations](https://alembic.sqlalchemy.org/en/latest/cookbook.html#asyncio)
- TimescaleDB — hypertables, continuous aggregates, retention/compression policies

---

*Draft v1 prepared 22 May 2026 by Beyza Ülkümen. To be reviewed by Abdullah (M1W2T6). Final committed to `/docs/api/fastapi_project_structure.md` on GitHub by Friday 23 May (M1W2T16).*
