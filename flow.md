# End-to-End Code Execution & Control Flow Map (`flow.md`)

This document maps **how execution travels through files, functions, and modules** across the entire **Vendor Intelligence** system. It details the exact call sequences, execution orders, active execution paths, and an audit trail of all AI modifications made during sessions.

---

## 📑 Table of Contents

- [End-to-End Code Execution & Control Flow Map (`flow.md`)](#end-to-end-code-execution--control-flow-map-flowmd)
  - [📑 Table of Contents](#-table-of-contents)
  - [📍 Quick Reference: Active Modification Focal Point](#-quick-reference-active-modification-focal-point)
  - [🚀 System Bootstrapping & Entry Points](#-system-bootstrapping--entry-points)
    - [1. Backend Boot Sequence (`backend/app/main.py`)](#1-backend-boot-sequence-backendappmainpy)
    - [2. Frontend Client Initialization Sequence (`frontend/js/app.js`)](#2-frontend-client-initialization-sequence-frontendjsappjs)
  - [🔄 Detailed Function-to-Function Execution Flows](#-detailed-function-to-function-execution-flows)
    - [Flow 1: Single Invoice Risk Scoring (`POST /api/invoice/predict`)](#flow-1-single-invoice-risk-scoring-post-apiinvoicepredict)
    - [Flow 2: Freight Cost Estimation (`POST /api/freight/predict`)](#flow-2-freight-cost-estimation-post-apifreightpredict)
    - [Flow 3: CSV Batch Ingestion & Asynchronous Processing (`POST /api/invoice/batch-upload`)](#flow-3-csv-batch-ingestion--asynchronous-processing-post-apiinvoicebatch-upload)
    - [Flow 4: RAG Audit Explanation & Natural Language Assistant (`/api/rag/*`)](#flow-4-rag-audit-explanation--natural-language-assistant-apirag)
    - [Flow 5: Database Connection & Failover Lifecycle (`backend/app/database.py`)](#flow-5-database-connection--failover-lifecycle-backendappdatabasepy)
  - [🗺️ Module-to-Module Call Hierarchy Matrix](#️-module-to-module-call-hierarchy-matrix)
  - [📜 AI Session Change Ledger](#-ai-session-change-ledger)

---

## 📍 Quick Reference: Active Modification Focal Point
    
| Attribute | Current Value |
| :--- | :--- |
| **Active Session Target** | Documentation & Execution Architecture Mapping |
| **Current Target File** | [`flow.md`](file:///d:/newvendor/vendor-intelligence-main/flow.md) & [`decision.md`](file:///d:/newvendor/vendor-intelligence-main/decision.md) |
| **Affected Layer** | Documentation & Architecture Observability |
| **Execution Path Impacted** | Complete System Traceability (Presentation $\rightarrow$ Gateway $\rightarrow$ Service $\rightarrow$ ML $\rightarrow$ Persistence) |
| **Status** | In Progress (Documenting full execution flows & change history) |

---

## 🚀 System Bootstrapping & Entry Points

### 1. Backend Boot Sequence (`backend/app/main.py`)

When the backend is started via `uvicorn app.main:app --reload` or `python -m uvicorn`:

```mermaid
sequenceDiagram
    autonumber
    participant CLI as Uvicorn CLI
    participant Main as backend/app/main.py
    participant DB as backend/app/database.py
    participant ML as backend/app/ml_models.py
    participant Routers as backend/app/routers/*
    participant BP as backend/app/batch_processor.py
    participant Static as FastAPI StaticFiles

    CLI->>Main: Import module app.main:app
    Main->>DB: Base.metadata.create_all(bind=engine)
    DB->>DB: Attempt PostgreSQL connection -> (Fallback to SQLite if failed)
    Main->>ML: Import ml_models (Triggers module-level joblib.load for scaler & models)
    ML-->>Main: Models loaded into memory singleton
    Main->>Routers: app.include_router(invoice, freight, rag, batches)
    Main->>Static: app.mount("/", StaticFiles(directory="frontend"))
    CLI->>Main: Trigger startup event (@app.on_event("startup"))
    Main->>BP: batch_processor.cleanup_stuck_batches(db, max_minutes=30)
    BP-->>Main: Cleanup completed
    Main-->>CLI: ASGI Application Ready (Listening on http://127.0.0.1:8000)
```

#### Detailed Step-by-Step Code Walkthrough:
1. **Module Import**: `uvicorn` imports [main.py](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py#L1-L23).
2. **Database Binding**: [main.py:16](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py#L16) calls `Base.metadata.create_all(bind=engine)`.
   - [database.py:24-34](file:///d:/newvendor/vendor-intelligence-main/backend/app/database.py#L24-L34) runs `create_engine()`. If PostgreSQL connection raises `OperationalError`, it falls back to SQLite `sqlite:///./vendor_intelligence.db`.
3. **ML Model Preloading**: Importing [ml_models.py:24-26](file:///d:/newvendor/vendor-intelligence-main/backend/app/ml_models.py#L24-L26) executes `joblib.load()` for:
   - `scaler.pkl` (`StandardScaler`)
   - `predict_flag_invoice.pkl` (`RandomForestClassifier`)
   - `predict_freight_model.pkl` (`LinearRegression`)
4. **Middleware & Routers**:
   - [main.py:36-42](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py#L36-L42) mounts `CORSMiddleware`.
   - [main.py:44-47](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py#L44-L47) includes `invoice.router`, `freight.router`, `rag.router`, `batches.router`.
5. **Startup Event**: [main.py:25-33](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py#L25-L33) `startup_event()` executes:
   - Calls [batch_processor.py:cleanup_stuck_batches](file:///d:/newvendor/vendor-intelligence-main/backend/app/batch_processor.py#L440-L468) to mark orphan jobs older than 30 mins as `FAILED`.

---

### 2. Frontend Client Initialization Sequence (`frontend/js/app.js`)

When a user opens `http://localhost:8000/` in the browser:

```mermaid
sequenceDiagram
    autonumber
    participant Browser as Browser Window
    participant HTML as index.html
    participant AppJS as frontend/js/app.js
    participant API as FastAPI Backend

    Browser->>HTML: GET / (Loads index.html)
    HTML->>AppJS: Executes app.js
    AppJS->>AppJS: Cache DOM element references (forms, buttons, tables)
    AppJS->>AppJS: Attach Event Listeners (Nav tabs, Submit handlers, Filter dropdowns)
    AppJS->>API: GET /api/invoice/history (Initial dashboard history table load)
    API-->>AppJS: Returns recent 50 predictions JSON
    AppJS->>HTML: Render table rows in #historyTableBody
```

---

## 🔄 Detailed Function-to-Function Execution Flows

### Flow 1: Single Invoice Risk Scoring (`POST /api/invoice/predict`)

**Purpose**: User submits a single invoice through the web UI form or API client to detect fraud or risk.

```mermaid
flowchart TD
    A["👤 User Form Submit (index.html)"] -->|Event: submit| B["JS: invoiceForm handler (frontend/js/app.js)"]
    B -->|Fetch POST /api/invoice/predict| C["Router: predict_invoice() (backend/app/routers/invoice.py)"]
    C -->|Validate schema| D["Schema: schemas.InvoiceInput (backend/app/schemas.py)"]
    D -->|Call service| E["Service: services.score_and_save_invoice() (backend/app/services.py)"]
    E -->|Prepare 5-feature vector| F["ML: ml_models.predict_invoice_flag() (backend/app/ml_models.py)"]
    F -->|scaler.transform()| G["StandardScaler (scaler.pkl)"]
    G -->|flag_model.predict() & predict_proba()| H["RandomForestClassifier (predict_flag_invoice.pkl)"]
    H -->|Return (flag, prob)| F
    F -->|Return tuple| E
    E -->|Instantiate ORM & db.commit()| I["DB: models_db.InvoicePrediction (Postgres / SQLite)"]
    I -->|Return ORM instance| C
    C -->|Serialize response| J["Schema: schemas.InvoicePredictionOut"]
    J -->|JSON Response| B
    B -->|Render UI badge & probability bar| K["Browser DOM: #invoiceResult"]
```

#### Exact Step-by-Step Call Trace:
1. **Frontend**: [`frontend/js/app.js`](file:///d:/newvendor/vendor-intelligence-main/frontend/js/app.js) collects form inputs: `invoice_quantity`, `invoice_dollars`, `freight`, `total_item_quantity`, `total_item_dollars`, `vendor_number`, `po_number`, `invoice_date`.
2. **HTTP Request**: Dispatches `POST /api/invoice/predict` with JSON body.
3. **Gateway Router**: [`backend/app/routers/invoice.py:predict_invoice`](file:///d:/newvendor/vendor-intelligence-main/backend/app/routers/invoice.py#L12-L41) receives request.
4. **Validation**: Pydantic validates input via [`schemas.InvoiceInput`](file:///d:/newvendor/vendor-intelligence-main/backend/app/schemas.py).
5. **Business Service**: Calls [`services.score_and_save_invoice`](file:///d:/newvendor/vendor-intelligence-main/backend/app/services.py#L10-L63).
6. **ML Inference**:
   - Calls [`ml_models.predict_invoice_flag`](file:///d:/newvendor/vendor-intelligence-main/backend/app/ml_models.py#L29-L41).
   - Formats Pandas DataFrame with `FLAG_FEATURE_ORDER` = `["invoice_quantity", "invoice_dollars", "Freight", "total_item_quantity", "total_item_dollars"]`.
   - Executes `scaler.transform(row)`.
   - Executes `flag_model.predict(row_scaled)` and `flag_model.predict_proba(row_scaled)`.
7. **Database Persistence**: Instantiates [`models_db.InvoicePrediction`](file:///d:/newvendor/vendor-intelligence-main/backend/app/models_db.py), calls `db.add(record)`, `db.commit()`, `db.refresh(record)`.
8. **Response Formatting**: Returns [`schemas.InvoicePredictionOut`](file:///d:/newvendor/vendor-intelligence-main/backend/app/schemas.py) with `risk_label` (`FLAGGED` or `CLEARED`) and `risk_probability`.
9. **UI Update**: `app.js` renders badge, score meter, and appends the new record to the history table.

---

### Flow 2: Freight Cost Estimation (`POST /api/freight/predict`)

**Purpose**: User submits invoice dollar amount to estimate freight cost.

```mermaid
flowchart TD
    A["👤 User Form Submit (index.html)"] -->|Event: submit| B["JS: freightForm handler (frontend/js/app.js)"]
    B -->|Fetch POST /api/freight/predict| C["Router: predict_freight() (backend/app/routers/freight.py)"]
    C -->|Validate schema| D["Schema: schemas.FreightInput (backend/app/schemas.py)"]
    D -->|Call service| E["Service: services.score_and_save_freight() (backend/app/services.py)"]
    E -->|Call ML pipeline| F["ML: ml_models.predict_freight() (backend/app/ml_models.py)"]
    F -->|freight_model.predict(Dollars)| G["LinearRegression (predict_freight_model.pkl)"]
    G -->|Raw estimate| F
    F -->|Clamp: max(0.0, min(raw, dollars))| E
    E -->|db.add & db.commit()| H["DB: models_db.FreightPrediction (Postgres / SQLite)"]
    H -->|Return ORM instance| C
    C -->|Serialize response| I["Schema: schemas.FreightPredictionOut"]
    I -->|JSON Response| B
    B -->|Display estimated freight & ratio| J["Browser DOM: #freightResult"]
```

#### Exact Step-by-Step Call Trace:
1. **Frontend**: [`frontend/js/app.js`](file:///d:/newvendor/vendor-intelligence-main/frontend/js/app.js) sends `dollars` (and optional metadata `vendor_number`, `po_number`, `invoice_date`).
2. **HTTP Request**: `POST /api/freight/predict`.
3. **Router**: [`backend/app/routers/freight.py:predict_freight`](file:///d:/newvendor/vendor-intelligence-main/backend/app/routers/freight.py).
4. **Service**: [`services.score_and_save_freight`](file:///d:/newvendor/vendor-intelligence-main/backend/app/services.py#L66-L97).
5. **ML Inference**: [`ml_models.predict_freight`](file:///d:/newvendor/vendor-intelligence-main/backend/app/ml_models.py#L44-L57):
   - Executes linear regression prediction.
   - Applies safety clamp: `max(0.0, min(raw, dollars))` to prevent negative freight or freight exceeding total invoice value.
6. **Persistence**: Saves [`models_db.FreightPrediction`](file:///d:/newvendor/vendor-intelligence-main/backend/app/models_db.py) to database.
7. **Response**: Returns [`schemas.FreightPredictionOut`](file:///d:/newvendor/vendor-intelligence-main/backend/app/schemas.py).

---

### Flow 3: CSV Batch Ingestion & Asynchronous Processing (`POST /api/invoice/batch-upload`)

**Purpose**: High-volume ingestion of multi-thousand row CSV files with deduplication, validation, ML scoring, and progress tracking.

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser (Upload Form)
    participant Router as routers/invoice.py
    participant BP as batch_processor.py
    participant DB as Database (Postgres/SQLite)
    participant ML as ml_models.py & services.py
    participant BG as FastAPI BackgroundTasks

    UI->>Router: POST /api/invoice/batch-upload (multipart/form-data CSV)
    Router->>BP: check_and_create_batch(db, filename, content, "INVOICE")
    BP->>BP: compute_file_hash(content) -> SHA-256
    BP->>DB: Check if file_hash exists in UploadBatch
    alt Whole-file duplicate
        BP-->>Router: Raise HTTP 400 (Duplicate file already processed)
        Router-->>UI: Return 400 Bad Request
    else New file
        BP->>DB: Insert UploadBatch(status='PROCESSING')
        BP-->>Router: Return batch instance
    end

    Router->>Router: Estimate line count (content.count(b'\n'))
    
    alt Small Batch (<= 500 rows)
        Router->>BP: process_invoice_batch_sync(db, batch_id, content)
        BP->>BP: decode_csv_content() (utf-8-sig / utf-8 / latin-1)
        BP->>BP: Validate required column headers
        loop Each Chunk of 500 rows
            BP->>BP: Validate row fields & sanity dollar ceiling ($10M)
            BP->>BP: Check intra-batch duplicate hash
            BP->>ML: services.score_and_save_invoice(commit=False)
            BP->>DB: db.bulk_save_objects() & db.commit()
        end
        BP->>DB: Update UploadBatch(status='COMPLETED', success_count, duplicate_count)
        BP-->>Router: Return completed batch
        Router-->>UI: Return 200 JSON with summary metrics
    else Large Batch (> 500 rows)
        Router->>BG: background_tasks.add_task(run_bg, batch.id, content)
        Router-->>UI: Return 202 Accepted (status='PROCESSING', is_async=true, batch_uuid)
        UI->>Router: Poll GET /api/invoice/batch-status/{batch_uuid} every 2s
        BG->>BP: process_invoice_batch_sync(bg_db, batch_id, content)
        BP->>DB: Periodic progress flush (rows_processed, status='COMPLETED')
        Router-->>UI: Polling returns status='COMPLETED' -> Render full batch results
    end
```

---

### Flow 4: RAG Audit Explanation & Natural Language Assistant (`/api/rag/*`)

**Purpose**: AI-assisted anomaly audit explanation (`/api/invoice/{id}/explain`) and natural language conversational querying (`POST /api/rag/query`).

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser Chat UI (rag.js)
    participant Router as routers/rag.py or routers/invoice.py
    participant Service as rag_service.py
    participant DB as Database Session
    participant Gemini as Google GenAI (Gemini-1.5)

    UI->>Router: POST /api/rag/query {"question": "Which vendors had highest flagged invoices?"}
    Router->>Service: rag_service.handle_query(db, question)
    Service->>Service: Parse intent (Aggregation / Vendor Audit / Rule Explanations)
    Service->>DB: Query historical metrics (e.g., top flagged vendors, total dollar discrepancies)
    DB-->>Service: Metric results dataset
    Service->>Service: Format RAG Context Prompt (Schema + DB Findings + Guidelines)
    Service->>Gemini: Invoke ChatGoogleGenerativeAI.invoke(prompt)
    Gemini-->>Service: Formatted Markdown response with reasoning & references
    Service-->>Router: Structured RAG response
    Router-->>UI: Return JSON {answer, context_records, query_type}
    UI->>UI: Render markdown response bubble & supporting data tables
```

---

### Flow 5: Database Connection & Failover Lifecycle (`backend/app/database.py`)

**Purpose**: Handles primary connection to PostgreSQL with zero-downtime automatic fallback to SQLite.

```mermaid
flowchart TD
    A["API Startup / DB Call"] --> B["database.py: engine initialization"]
    B -->|Try Primary| C{"Connect PostgreSQL (settings.database_url)"}
    C -->|Success| D["Bind SessionLocal to PostgreSQL Engine"]
    C -->|Raises OperationalError| E["Log Warning: PostgreSQL unavailable"]
    E -->|Fallback| F["Initialize SQLite: sqlite:///./vendor_intelligence.db"]
    F -->|Configure Engine| G["Set StaticPool, check_same_thread=False"]
    G --> D
    D --> H["FastAPI Depends(get_db) yields DB Session"]
    H --> I["Route / Service executes SQL operations"]
    I --> J["db.close() inside finally block"]
```

---

## 🗺️ Module-to-Module Call Hierarchy Matrix

| Caller Module | Called Function / Class | Target File | Purpose |
| :--- | :--- | :--- | :--- |
| `main.py` | `Base.metadata.create_all()` | [`database.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/database.py) | Initialize DB schema |
| `main.py` | `cleanup_stuck_batches()` | [`batch_processor.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/batch_processor.py) | Recover orphaned batch jobs on startup |
| `main.py` | `include_router()` | [`routers/*.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/routers) | Register REST API endpoints |
| `routers/invoice.py` | `score_and_save_invoice()` | [`services.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/services.py) | Single invoice risk scoring & DB save |
| `routers/invoice.py` | `check_and_create_batch()` | [`batch_processor.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/batch_processor.py) | Validate and track CSV batch |
| `routers/invoice.py` | `explain_invoice_flag()` | [`rag_service.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/rag_service.py) | Generate Gemini RAG audit explanation |
| `routers/freight.py` | `score_and_save_freight()` | [`services.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/services.py) | Single freight cost estimation |
| `routers/rag.py` | `handle_query()` | [`rag_service.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/rag_service.py) | Natural language queries & RAG analytics |
| `services.py` | `predict_invoice_flag()` | [`ml_models.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/ml_models.py) | Scikit-Learn scaler + RandomForest |
| `services.py` | `predict_freight()` | [`ml_models.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/ml_models.py) | LinearRegression freight model |
| `batch_processor.py` | `score_and_save_invoice()` | [`services.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/services.py) | Reusable scoring for batch rows |

---

## 📜 AI Session Change Ledger

This ledger tracks **every code modification performed by the AI agent** in chronological order, recording the exact path, functions, and rationale.

### Session Log Index

| Change ID | Timestamp | Target File(s) | Functions / Components Touched | Description of Changes |
| :--- | :--- | :--- | :--- | :--- |
| **CHG-0001** | 2026-09-12 13:19 | [`decision.md`](file:///d:/newvendor/vendor-intelligence-main/decision.md) | Whole file (New) | Created Architecture & Design Decision Log (`decision.md`) with ADR-0001 to ADR-0008, template, and logging guidelines. |
| **CHG-0002** | 2026-09-12 13:33 | [`flow.md`](file:///d:/newvendor/vendor-intelligence-main/flow.md) | Whole file (New) | Created Execution Flow & Call Graph Map (`flow.md`) documenting complete entry points, execution chains, Mermaid sequence diagrams, and active modification tracking. |

---

### Change Detail Records

#### CHG-0001: Architecture Decision Record Log Initialization
- **Timestamp**: 2026-09-12 13:19:06 IST
- **Target File**: [`d:/newvendor/vendor-intelligence-main/decision.md`](file:///d:/newvendor/vendor-intelligence-main/decision.md)
- **Component**: Project Architecture & Documentation
- **What was changed**:
  - Implemented formal ADR framework with standard template.
  - Documented ADR-0001 through ADR-0008 covering FastAPI, PostgreSQL/SQLite Dual Engine, Joblib serialization, SHA-256 deduplication, Vanilla JS frontend, LangChain GenAI, Layered architecture, and Pydantic v2 validation.
- **Execution Path Affected**: System-wide architectural documentation.

#### CHG-0002: Execution Flow & Control Flow Mapping
- **Timestamp**: 2026-09-12 13:33:40 IST
- **Target File**: [`d:/newvendor/vendor-intelligence-main/flow.md`](file:///d:/newvendor/vendor-intelligence-main/flow.md)
- **Component**: Execution Flow Observability & Call Tree Documentation
- **What was changed**:
  - Documented backend startup sequence ([`backend/app/main.py`](file:///d:/newvendor/vendor-intelligence-main/backend/app/main.py)).
  - Documented frontend client initialization ([`frontend/js/app.js`](file:///d:/newvendor/vendor-intelligence-main/frontend/js/app.js)).
  - Detailed function-by-function execution flows for Invoice Scoring, Freight Estimation, Batch Uploads, RAG Assistant, and Database Failover.
  - Added module call hierarchy matrix and AI session change ledger.
- **Execution Path Affected**: Observability across all backend and frontend execution paths.
