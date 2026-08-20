# Vendor Intelligence — Setup Guide (Beginner Friendly)

This project has two of your trained models wired into a small web app:

- **Invoice Risk Check** → uses `scaler.pkl` + `predict_flag_invoice.pkl` (Random Forest)
- **Freight Cost Estimate** → uses `predict_freight_model.pkl` (Linear Regression)

Every prediction is saved to a **Postgres** database so you keep a history of what was checked.

## 1. Project structure

```
vendor_intelligence/
├── backend/                     ← FastAPI app (Python)
│   ├── app/
│   │   ├── main.py              ← starts the server, wires everything together
│   │   ├── config.py            ← reads settings from .env
│   │   ├── database.py          ← Postgres connection setup
│   │   ├── models_db.py         ← Postgres TABLE definitions (SQLAlchemy)
│   │   ├── schemas.py           ← Pydantic request/response validation
│   │   ├── ml_models.py         ← loads your .pkl files and runs predictions
│   │   └── routers/
│   │       ├── invoice.py       ← /api/invoice/... endpoints
│   │       └── freight.py       ← /api/freight/... endpoints
│   ├── models/                  ← your 3 .pkl files live here
│   ├── requirements.txt
│   └── .env.example             ← copy to .env and fill in your Postgres password
│
└── frontend/                    ← plain HTML/CSS/JS, no build step needed
    ├── index.html
    ├── css/style.css
    └── js/app.js
```

This separation (backend does data + ML, frontend does the visuals) is the standard
way real web apps are structured — keep following this pattern as the project grows.

## 2. Install Postgres and create the database

1. Install Postgres (postgresql.org, or `sudo apt install postgresql` on Ubuntu).
2. Open a terminal and create the database:
   ```bash
   psql -U postgres
   CREATE DATABASE vendor_intelligence;
   \q
   ```
   You don't need to create tables manually — the FastAPI app creates
   `invoice_predictions` and `freight_predictions` automatically the first
   time it starts.

## 3. Configure the backend

```bash
cd vendor_intelligence/backend
cp .env.example .env
```
Open `.env` and put in your real Postgres username/password:
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_real_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vendor_intelligence
```

## 4. Install Python dependencies and run the backend

```bash
cd vendor_intelligence/backend
python -m venv venv

# activate it:
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt

uvicorn app.main:app --reload
```

You should see something like `Uvicorn running on http://127.0.0.1:8000`.

Visit **http://localhost:8000/docs** — this is FastAPI's automatic interactive
API documentation. You can test both endpoints there before ever touching the frontend.

## 5. Open the frontend

The backend already serves the frontend for you at the same address, so just open:

**http://localhost:8000/**

(That's it — no separate server, no build tools, because `main.py` mounts the
`frontend/` folder directly.)

If you ever prefer to run the frontend separately (e.g. with VS Code's "Live
Server" extension on port 5500), open `frontend/js/app.js` and it will
automatically point itself at `http://localhost:8000` for the API.

## 6. Using the app

- **Invoice Risk Check**: fill in the 5 invoice/PO fields and click "Stamp this
  invoice." You'll get a CLEARED or FLAGGED stamp with a confidence percentage.
- **Freight Cost Estimate**: enter an invoice dollar amount and click "Estimate
  freight" to get a projected freight cost.
- Both panels log every prediction into Postgres, and the **Recent entries**
  tables at the bottom show your history (click Refresh to reload it).

## 7. How a request flows through the code (for learning)

1. You submit the form in `index.html` → `js/app.js` catches the submit event.
2. `app.js` sends a `fetch()` POST request with JSON to e.g. `/api/invoice/predict`.
3. FastAPI (`routers/invoice.py`) receives it. Pydantic (`schemas.py`)
   automatically checks the JSON matches `InvoiceInput` — wrong types or
   missing fields get rejected with a clear error before your code even runs.
4. The router calls `ml_models.predict_invoice_flag(...)`, which scales the
   features with `scaler.pkl` and asks `predict_flag_invoice.pkl` for a verdict.
5. The router saves the result as a row in Postgres via SQLAlchemy
   (`models_db.py`), then returns a JSON response shaped by `InvoicePredictionOut`.
6. `app.js` receives that JSON and renders the stamp / updates the table.

## 8. Common beginner issues

| Problem | Likely fix |
|---|---|
| "could not connect to server" / DB errors | Postgres isn't running, or `.env` has the wrong password/port |
| CORS error in browser console | Make sure you're opening the app through `http://localhost:8000/`, or add your frontend's port to `allowed_origins` in `config.py` |
| `ModuleNotFoundError` | You forgot to `pip install -r requirements.txt` inside the activated virtual environment |
| Predictions look wrong / errors from the model | Make sure the 3 `.pkl` files are inside `backend/models/` exactly as shipped — don't retrain/replace one without the others, since the scaler and flag model must match |

## 9. Where your existing training scripts fit in

Your `train.py`, `data_preprocessing.py`, and `modeling_evaluation.py` /
`model_evaluation.py` files are **not part of the running web app** — they're
what you (or the data team) run *offline* to (re)train the models and produce
new `.pkl` files. When a new model is ready, just drop the new `.pkl` into
`backend/models/`, replacing the old one, and restart `uvicorn`. Keep those
training scripts in a separate `training/` folder alongside `backend/` and
`frontend/` if you want to keep them in the same project going forward.
