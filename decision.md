# Architectural & Technical Decision Log (`decision.md`)

This document serves as the single source of truth for all architectural, library, and pattern decisions across the **Vendor Intelligence** system.

Every time code changes are introduced—whether adopting a new library, refactoring design patterns, adjusting database behaviors, or accepting architectural trade-offs—they **must be documented here** using the [Decision Record Template](#-decision-record-template).

---

## 📑 Table of Contents

- [Architectural & Technical Decision Log (`decision.md`)](#architectural--technical-decision-log-decisionmd)
  - [📑 Table of Contents](#-table-of-contents)
  - [📋 Guidelines for Logging Decisions](#-guidelines-for-logging-decisions)
  - [📝 Decision Record Template](#-decision-record-template)
  - [🏛️ Existing Architectural Decision Records (ADRs)](#️-existing-architectural-decision-records-adrs)
    - [ADR-0001: FastAPI Framework for High-Performance REST Gateway](#adr-0001-fastapi-framework-for-high-performance-rest-gateway)
    - [ADR-0002: Dual Database Strategy (PostgreSQL Primary with SQLite Failover)](#adr-0002-dual-database-strategy-postgresql-primary-with-sqlite-failover)
    - [ADR-0003: Joblib Model Serialization with Scikit-Learn Inference Pipeline](#adr-0003-joblib-model-serialization-with-scikit-learn-inference-pipeline)
    - [ADR-0004: SHA-256 Pre-Inference Deduplication in Batch Processing](#adr-0004-sha-256-pre-inference-deduplication-in-batch-processing)
    - [ADR-0005: Vanilla HTML5/CSS/JavaScript Frontend over SPA Frameworks](#adr-0005-vanilla-html5cssjavascript-frontend-over-spa-frameworks)
    - [ADR-0006: LangChain Google GenAI Integration for RAG & Analytics](#adr-0006-langchain-google-genai-integration-for-rag--analytics)
    - [ADR-0007: Layered Architecture (Routers -> Services -> Models -> DB)](#adr-0007-layered-architecture-routers---services---models---db)
    - [ADR-0008: Pydantic v2 for Input/Output Validation & Data Contracts](#adr-0008-pydantic-v2-for-inputoutput-validation--data-contracts)
  - [🔄 Ongoing & Future Decision Log](#-ongoing--future-decision-log)

---

## 📋 Guidelines for Logging Decisions

Whenever you modify code or make design choices:
1. **Explain the "Why"**: Don't just list what was changed; explain the problem and the root motivation.
2. **Library Comparison**: State explicitly why library $X$ was chosen over $Y$ (e.g., speed, memory, compatibility, community support).
3. **Pattern Rationale**: Explain why a particular software design pattern (e.g., Factory, Strategy, Repository, Dependency Injection) was applied.
4. **Trade-offs Accepted**: Document what we sacrificed (e.g., development time vs. runtime speed, flexibility vs. strict safety) and why that compromise is acceptable.
5. **Consequences & Follow-ups**: Mention downstream impacts, potential technical debt, or future migration paths.

---

## 📝 Decision Record Template

Use this format when appending a new decision:

```markdown
### ADR-XXXX: [Short Descriptive Title]

- **Date**: YYYY-MM-DD
- **Status**: Proposed | Accepted | Deprecated | Superseded by ADR-YYYY
- **Author(s)**: [Name/Role]
- **Component(s)**: [Backend / Frontend / Database / ML / RAG / CI-CD]

#### 1. Context & Problem Statement
[Describe the business requirement, performance bottleneck, bug, or technical challenge that necessitated this change.]

#### 2. Decision Taken
[Describe what was decided, implemented, or changed.]

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **Option A (Chosen)** | ... | ... | Selected because ... |
| **Option B (Alternative)** | ... | ... | Rejected because ... |
| **Option C (Alternative)** | ... | ... | Rejected because ... |

#### 4. Design Pattern & Architecture Rationale
[Explain why this specific code pattern or abstraction was chosen, e.g., Strategy pattern, Decorator, Dependency Injection, Event-driven.]

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: [e.g., Higher memory consumption accepted for sub-millisecond lookups]
- **Trade-off**: [e.g., Increased boilerplate accepted for strict type safety]

#### 6. Consequences & Impact
- **Positive**: [Benefits achieved]
- **Negative / Risks**: [Known limitations or maintenance burdens]
- **Mitigation**: [How risks are monitored or mitigated]
```

---

## 🏛️ Existing Architectural Decision Records (ADRs)

### ADR-0001: FastAPI Framework for High-Performance REST Gateway

- **Date**: 2026-03-01
- **Status**: Accepted
- **Component(s)**: Backend (`backend/app/main.py`, `backend/app/routers/`)

#### 1. Context & Problem Statement
The application requires a low-latency backend to serve synchronous ML predictions (single-item invoice risk & freight cost estimations) as well as handle asynchronous chunked batch file uploads without blocking the event loop.

#### 2. Decision Taken
Selected **FastAPI** running on top of **Uvicorn (ASGI)** as the backend framework.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **FastAPI (Chosen)** | Native async/await, native Pydantic v2 validation, automatic OpenAPI/Swagger docs, high throughput. | Relatively lightweight (requires manual ORM/auth setup compared to batteries-included frameworks). | **Selected**: Best-in-class performance for ML microservices, automated schema generation, robust async support. |
| **Flask** | Mature ecosystem, simple mental model. | WSGI-native (blocking), requires external plugins (`flask-pydantic`, `flasgger`) for modern validation and docs. | **Rejected**: Slower async handling; extra glue code required for typing and OpenAPI. |
| **Django / Django REST Framework** | Batteries-included, built-in ORM & admin dashboard. | Heavy footprint, slower startup, monolithic overhead unnecessary for an ML API service. | **Rejected**: Unnecessary architectural complexity for a microservice and ML serving system. |

#### 4. Design Pattern & Architecture Rationale
- **APIRouter modularity**: Routes are divided into domain-specific modules (`invoice.py`, `freight.py`, `batches.py`, `rag.py`) to maintain separation of concerns.
- **Dependency Injection**: FastAPI's `Depends` is used for database session lifecycle management (`get_db`), ensuring clean session teardown.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: FastAPI does not provide a built-in admin panel like Django.
- **Acceptance**: Acceptable because our frontend provides dedicated administrative and analytical dashboards.

#### 6. Consequences & Impact
- Sub-50ms API responses for ML inference.
- Automatic interactive documentation at `/docs`.

---

### ADR-0002: Dual Database Strategy (PostgreSQL Primary with SQLite Failover)

- **Date**: 2026-03-05
- **Status**: Accepted
- **Component(s)**: Persistence Layer (`backend/app/database.py`, `backend/app/models_db.py`)

#### 1. Context & Problem Statement
In enterprise environments and local development environments, PostgreSQL might occasionally experience connection drops, network partition, or unconfigured credentials. The application must not crash completely during local testing or temporary DB downtime.

#### 2. Decision Taken
Implemented an **Automated Failover Engine** via SQLAlchemy: attempt connection to PostgreSQL; if the connection fails, log a warning and fall back seamlessly to a local `vendor_intelligence.db` SQLite database.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **SQLAlchemy 2.0 ORM + Dual Engine (Chosen)** | Unified data model definition (`models_db.py`), transparent switching between dialects (PostgreSQL / SQLite). | SQLite does not support all PostgreSQL features (e.g., native JSONB indexing, concurrent write locks). | **Selected**: Allows true offline/standby resilience without changing application business code. |
| **Raw psycopg2 / asyncpg** | Maximum raw speed. | No ORM abstraction; dialect switching requires duplicate SQL queries for SQLite and Postgres. | **Rejected**: Increases code duplication and maintenance burden. |

#### 4. Design Pattern & Architecture Rationale
- **Factory & Fallback Pattern**: `create_engine` wrapper catches `OperationalError` during initialization and initializes SQLite fallback engine with `StaticPool` and `check_same_thread=False`.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: SQLite has file-level locking during heavy concurrent batch writes.
- **Acceptance**: Acceptable for fallback/local development; production clusters use persistent PostgreSQL instances.

---

### ADR-0003: Joblib Model Serialization with Scikit-Learn Inference Pipeline

- **Date**: 2026-03-10
- **Status**: Accepted
- **Component(s)**: Intelligence Layer (`backend/app/ml_models.py`, `backend/models/*.pkl`)

#### 1. Context & Problem Statement
Trained models (`RandomForestClassifier`, `LinearRegression`, and `StandardScaler`) need to be loaded into memory once on server startup and evaluated with zero cold-start overhead per request.

#### 2. Decision Taken
Serialized models using `joblib` (`.pkl`) and created a thread-safe singleton wrapper in `ml_models.py` loaded during application lifespan.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **Joblib (Chosen)** | Optimized for objects with large NumPy arrays, fast disk I/O, native scikit-learn standard. | Pickled objects are Python-version and library-version sensitive. | **Selected**: Zero-overhead loading for Scikit-Learn pipelines. |
| **ONNX Runtime** | Cross-platform, language-agnostic inference engine. | Requires model conversion step and custom scaler mapping. | **Rejected**: Added overhead with minimal latency gain given low model complexity. |
| **Standard `pickle`** | Built-in to Python standard library. | Slower serialization/deserialization for large numerical matrices compared to joblib. | **Rejected**: Joblib outperforms pickle on NumPy heavy objects. |

#### 4. Design Pattern & Architecture Rationale
- **Singleton Loader Pattern**: Models are loaded once into memory on API startup, eliminating disk read latency per inference call.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: Re-training requires reloading the API service or implementing hot-reload endpoints.
- **Acceptance**: Model updates are scheduled deployments, making hot-reloading unnecessary in Phase 1.

---

### ADR-0004: SHA-256 Pre-Inference Deduplication in Batch Processing

- **Date**: 2026-03-20
- **Status**: Accepted
- **Component(s)**: Batch Engine (`backend/app/batch_processor.py`)

#### 1. Context & Problem Statement
Large CSV batch uploads frequently contain duplicate invoice records or re-submitted purchase orders. Running ML inference and database writes on duplicate data wastes CPU cycles and creates database clutter.

#### 2. Decision Taken
Calculate a deterministic **SHA-256 hash** across normalized input row fields (`VendorID`, `PO_Number`, `Amount`, `ItemCategory`, `Timestamp`). Verify against database / in-memory cache before processing.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **SHA-256 Hashing (Chosen)** | Cryptographically collision-resistant, fast in standard library `hashlib`. | Slightly higher CPU cost than MD5/CRC32. | **Selected**: Collision immunity guarantees no accidental data loss. |
| **Database Unique Constraints only** | Handled natively by DB. | Incurs DB roundtrips and requires handling transaction rollbacks for entire batches. | **Rejected**: Fails early in-memory before invoking DB or ML pipeline. |

#### 4. Design Pattern & Architecture Rationale
- **Filter Pipeline / Guard Pattern**: Stream rows through deduplication filter before batch ML inference and bulk SQL inserts.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: Minor CPU overhead for hash computation per record.
- **Acceptance**: Saves significantly more time by bypassing Scikit-Learn pipeline and DB insert for duplicates.

---

### ADR-0005: Vanilla HTML5/CSS/JavaScript Frontend over SPA Frameworks

- **Date**: 2026-03-22
- **Status**: Accepted
- **Component(s)**: Frontend (`frontend/`)

#### 1. Context & Problem Statement
The application UI must be easy to deploy, fast to load, maintainable without heavy Node.js toolchains (`node_modules`, Webpack/Vite build steps), and directly servable via FastAPI static mount.

#### 2. Decision Taken
Built using modern **Vanilla HTML5, CSS3 Custom Properties (Design System), and Modular ES6+ JavaScript**.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **Vanilla HTML/CSS/JS (Chosen)** | Zero build step, instant refresh, zero npm dependency vulnerabilities, served directly by FastAPI `StaticFiles`. | Manual DOM updates for complex state trees. | **Selected**: Simple deployment, maximum performance, no build pipeline friction. |
| **React / Next.js** | Rich component ecosystem, declarative state management. | Requires Node.js build process, large bundle sizes, separate hosting or reverse proxy setup. | **Rejected**: Adds substantial build complexity for a dashboard application. |
| **Vue.js / Svelte** | Lightweight reactive framework. | Still introduces external build/bundler dependencies. | **Rejected**: Vanilla JS satisfies all UI requirements with zero dependencies. |

#### 4. Design Pattern & Architecture Rationale
- **Modular Component JS**: Separated logic into `app.js` (core/routing), `charts.js` (visualizations), `rag.js` (chat assistant).
- **CSS Custom Properties**: Centralized theme tokens (`--primary`, `--bg-dark`, `--accent`, `--border-color`) in `index.css` for consistent dark-mode styling.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: Requires explicit DOM manipulation functions (`document.getElementById`, `innerHTML`).
- **Acceptance**: UI complexity remains within manageable bounds, and performance is near-instant.

---

### ADR-0006: LangChain Google GenAI Integration for RAG & Analytics

- **Date**: 2026-04-02
- **Status**: Accepted
- **Component(s)**: AI & RAG Layer (`backend/app/rag_service.py`, `backend/app/routers/rag.py`)

#### 1. Context & Problem Statement
Users need intelligent querying, semantic search across historic invoices, anomaly explanations, and automated risk summaries via a natural language assistant.

#### 2. Decision Taken
Integrated **Google Gemini via `langchain-google-genai`** combined with contextual database lookups.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **LangChain Google GenAI (`gemini-1.5-pro/flash`) (Chosen)** | High context window (up to 1M+ tokens), fast reasoning, official LangChain integration for prompt templating. | Depends on Google API key availability and network connectivity. | **Selected**: Provides superior reasoning for financial risk analytics and structured JSON outputs. |
| **Local LLM (Ollama / Llama.cpp)** | Fully offline, no API key costs. | Requires local GPU hardware, higher memory consumption, slower inference. | **Rejected**: Target deployment environments may lack dedicated GPU accelerators. |
| **OpenAI GPT-4o** | High reasoning capability. | Higher token pricing and rate limits compared to Gemini tier for bulk invoice analytics. | **Rejected**: Google GenAI offers higher free tier limits and context capabilities. |

#### 4. Design Pattern & Architecture Rationale
- **Retrieval-Augmented Generation (RAG) Pattern**: Injects schema definitions, vendor metrics, and real-time query results directly into prompt context for grounded, hallucination-free financial analysis.

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: External API dependency for AI chat features.
- **Acceptance**: Fallback message is returned gracefully if the API key is missing or quota is exceeded, keeping core ML features functional.

---

### ADR-0007: Layered Architecture (Routers -> Services -> Models -> DB)

- **Date**: 2026-04-10
- **Status**: Accepted
- **Component(s)**: Backend Architecture (`backend/app/`)

#### 1. Context & Problem Statement
Mixing API request handling, business logic, ML inference, and database access inside single route handlers creates tight coupling, making testing and maintenance difficult.

#### 2. Decision Taken
Enforced strict **4-Layer Separation**:
1. **Routers (`routers/`)**: Pure HTTP request validation, status codes, and response serializing.
2. **Services (`services.py`, `batch_processor.py`, `rag_service.py`)**: Business logic, workflow orchestration, deduplication.
3. **Intelligence (`ml_models.py`)**: Model inference, feature scaling, prediction logic.
4. **Data Access (`models_db.py`, `database.py`)**: SQLAlchemy ORM models, session lifecycle, queries.

#### 3. Design Pattern & Architecture Rationale
- **Separation of Concerns (SoC)** & **Repository Pattern**: Allows unit tests to mock ML models or database sessions without running an actual server or database.

#### 4. Trade-offs & Accepted Compromises
- **Trade-off**: Requires writing multiple files/classes for a single feature.
- **Acceptance**: Maintainability and testability significantly improve as system features expand.

---

### ADR-0008: Pydantic v2 for Input/Output Validation & Data Contracts

- **Date**: 2026-04-15
- **Status**: Accepted
- **Component(s)**: Contracts & Schemas (`backend/app/schemas.py`)

#### 1. Context & Problem Statement
Invalid input data (e.g. negative freight weights, missing vendor IDs, incorrect date formats) can crash downstream Scikit-Learn pipelines with unhandled NumPy errors.

#### 2. Decision Taken
Used **Pydantic v2** with `Field(..., ge=0)` validation and custom validators to enforce strict contract boundaries before data reaches machine learning pipelines.

#### 3. Technology & Library Comparison (Why X over Y)
| Option Considered | Pros | Cons | Reason for Selection / Rejection |
| :--- | :--- | :--- | :--- |
| **Pydantic v2 (Chosen)** | Written in Rust (5x-10x faster than v1), strict type coercion, native FastAPI integration. | Strict model config syntax changes compared to v1. | **Selected**: Standard for modern Python API validation and performance. |
| **Marshmallow / Cerberus** | Established validation libraries. | Slower execution, requires extra adapters to integrate with FastAPI OpenAPI documentation. | **Rejected**: Lacks direct FastAPI synergy and Rust-based speed. |

#### 4. Design Pattern & Architecture Rationale
- **Data Transfer Object (DTO) Pattern**: Separate request models (`InvoicePredictRequest`, `FreightPredictRequest`) and response models (`InvoicePredictResponse`, `FreightPredictResponse`).

#### 5. Trade-offs & Accepted Compromises
- **Trade-off**: Strict validation rejects malformed requests with `422 Unprocessable Entity` rather than attempting silent coercion.
- **Acceptance**: Data integrity in financial/invoice auditing takes absolute precedence over loose parsing.

---

## 🔄 Ongoing & Future Decision Log

*Add new ADRs below as changes and refactoring take place.*

| ADR ID | Title | Date | Status | Area |
| :--- | :--- | :--- | :--- | :--- |
| [ADR-0001](#adr-0001-fastapi-framework-for-high-performance-rest-gateway) | FastAPI Framework for REST Gateway | 2026-03-01 | Accepted | Backend |
| [ADR-0002](#adr-0002-dual-database-strategy-postgresql-primary-with-sqlite-failover) | Dual Database Strategy (Postgres / SQLite) | 2026-03-05 | Accepted | Database |
| [ADR-0003](#adr-0003-joblib-model-serialization-with-scikit-learn-inference-pipeline) | Joblib Model Serialization | 2026-03-10 | Accepted | Machine Learning |
| [ADR-0004](#adr-0004-sha-256-pre-inference-deduplication-in-batch-processing) | SHA-256 Batch Deduplication | 2026-03-20 | Accepted | Batch Processing |
| [ADR-0005](#adr-0005-vanilla-html5cssjavascript-frontend-over-spa-frameworks) | Vanilla HTML5/CSS/JS Frontend | 2026-03-22 | Accepted | Frontend |
| [ADR-0006](#adr-0006-langchain-google-genai-integration-for-rag--analytics) | LangChain Google GenAI for RAG | 2026-04-02 | Accepted | AI & RAG |
| [ADR-0007](#adr-0007-layered-architecture-routers---services---models---db) | Layered Architecture (Routers -> Services -> DB) | 2026-04-10 | Accepted | Architecture |
| [ADR-0008](#adr-0008-pydantic-v2-for-inputoutput-validation--data-contracts) | Pydantic v2 Data Contracts | 2026-04-15 | Accepted | Validation |
