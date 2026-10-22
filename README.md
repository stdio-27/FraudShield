# 🛡️ FraudShield

FraudShield is an AI-powered Credit Card Fraud Detection and Analytics Platform that combines machine learning, real-time fraud scoring, TimescaleDB analytics, and an interactive React dashboard to help analysts detect and investigate fraudulent transactions.

---

## 🚀 Features

- 🔐 JWT-based authentication
- 🤖 AI-powered fraud prediction using XGBoost
- 📊 Interactive analytics dashboard
- 📈 Time-series fraud analytics with TimescaleDB
- 🚨 Fraud alert generation
- 📂 CSV dataset ingestion
- ⚡ FastAPI backend
- 🎨 React + Vite frontend
- 🐳 Docker support for PostgreSQL, TimescaleDB, Redis, and pgAdmin

---

# Tech Stack

## Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- TimescaleDB
- Redis
- Pydantic
- JWT Authentication

## Machine Learning

- XGBoost
- SHAP
- Scikit-learn
- Pandas
- Joblib

## Frontend

- React
- Vite
- Tailwind CSS
- Axios

## DevOps

- Docker
- Docker Compose

---

# Project Structure

```text
FraudShield
│
├── frontend/                 # React frontend
│
├── src/
│   ├── api/                  # FastAPI APIs
│   ├── database/             # Database configuration
│   └── ml/                   # ML utilities
│
├── models/                   # Trained ML models
│
├── scripts/                  # Data scripts
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# Installation

## 1. Clone Repository

```bash
git clone <repository-url>
cd FraudShield
```

---

## 2. Create Virtual Environment

Use Python 3.11 or 3.12 (the Docker image uses 3.12).

```bash
python3 -m venv .venv
```

Activate

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Only needed if you retrain the model:

```bash
pip install -r requirements-train.txt
```

---

## 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

# Environment Variables

Copy `.env.example` to `.env` in the project root and fill it in. The API and
`docker compose` both read this file. The important values:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required. Compose publishes the DB on `localhost:5433`. |
| `POSTGRES_PASSWORD`, `PGADMIN_PASSWORD` | Required by `docker compose`. |
| `SECRET_KEY` | JWT signing key (>= 32 chars). Mandatory when `APP_ENV=production`; in development a random per-process key is used if unset. |
| `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD` | First admin account (password >= 12 chars). There is no built-in default login. |
| `SCORING_API_KEY` | Optional key for machine clients of `POST /transactions/score` (`X-API-Key` header). |
| `REDIS_URL` | Optional; the API works without Redis (uncached, per-process rate limits). |

---

# Start Infrastructure

Run Docker services (ports are bound to `127.0.0.1` only):

```bash
docker compose up -d
```

This starts

- PostgreSQL + TimescaleDB (`localhost:5433`)
- Redis (`localhost:6379`)
- pgAdmin (`http://localhost:5050`)

---

# Train the Model

The repository's `models/` artifacts must be a consistent set. If the API
reports `artifacts_loaded: false` at `/health` (for example "Scaler was fitted
on 2 features"), retrain. This needs the dataset (see below) and
`requirements-train.txt`:

```bash
python -m src.ml.train
```

This writes `xgboost_fraud_model.json`, `scaler.joblib`, `amount_stats.json`
and `feature_manifest.json` (feature order, F1-optimal decision threshold,
SHA-256 of each artifact) to `models/`.

---

# Initialise the Database

Creates the tables, the first admin (from `SEED_ADMIN_*`) and imports the first
`DATASET_IMPORT_LIMIT` rows of the dataset (timestamps are shifted so the last
row is "now"):

```bash
python -m src.database.init_db
```

Use `--skip-dataset` to skip the import. Importing never happens implicitly
inside API requests.

To load a different amount later (e.g. the whole 284,807-row file), re-import
with `--replace-dataset`. It deletes only previously imported dataset rows (and
their alerts), keeps anything scored through the API, and works in chunks so
memory stays flat:

```bash
python -m src.database.init_db --replace-dataset --limit 0
```

`DATASET_IMPORT_LIMIT` only controls how much data is loaded for dashboard
testing. Training (`python -m src.ml.train`) always uses the entire CSV.

---

# Run Backend

```bash
uvicorn src.api.main:app --reload
```

Backend:

```
http://127.0.0.1:8000
```

Swagger UI:

```
http://127.0.0.1:8000/docs
```

---

# Run Frontend

```bash
cd frontend

npm run dev
```

Frontend:

```
http://localhost:5173
```

---

# Dataset

Download the Credit Card Fraud Detection dataset from Kaggle.

Place the file as `data/creditcard.csv` (or in the project root, or point
`DATASET_PATH` at it). It is used by `python -m src.ml.train` and
`python -m src.database.init_db`.

---

# Database Services

## PostgreSQL

```
localhost:5432
```

Database

```
fraudshield
```

---

## pgAdmin

```
http://localhost:5050
```

Log in with `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` from your
`.env`. pgAdmin only reads them when its data volume is first created; after
changing them, run `docker compose down -v` and `docker compose up -d`.

---

# API Documentation

Swagger

```
http://127.0.0.1:8000/docs
```

---

# Authentication

Login endpoint

```
POST /auth/login
```

Returns

```json
{
    "access_token": "...",
    "token_type": "bearer"
}
```

The frontend stores the JWT in Local Storage and automatically attaches it to authenticated requests.

- `POST /auth/register` is **admin-only** (bearer token of an admin); there is no self-service sign-up.
- Login is rate limited (`LOGIN_MAX_ATTEMPTS` per `LOGIN_WINDOW_SECONDS`, default 5 per 15 min).
- `POST /transactions/score` requires either an `X-API-Key: <SCORING_API_KEY>` header or an analyst/admin bearer token. It is idempotent on `transaction_id` and accepts an optional `transaction_time` (defaults to receipt time).
- Alerts: `GET /alerts?status=open,investigating&limit=50&offset=0` and `PATCH /alerts/{id}` (`{"status": "investigating"}`). Items include the top-5 SHAP `shap_reasons` plus the transaction's `amount`, `transaction_time` and `external_id`.
- `GET /health` returns 503 until the model artifacts are loaded and the database answers.

---

# Dashboard

The analytics dashboard includes

- Total Transactions
- Total Transaction Volume
- Flagged Incidents
- Average Risk Score
- Transaction Velocity
- Fraud Trend Analysis

---

# Machine Learning Pipeline

1. Load trained XGBoost model, scaler and manifest (validated at startup)
2. Engineer transaction features (`src/ml/features.py`, shared with training)
3. Predict fraud probability; flag at the threshold from `feature_manifest.json`
4. Generate SHAP explanations for flagged transactions
5. Store prediction in database
6. Create alerts for flagged transactions; fire the webhook at `ALERT_THRESHOLD`

Without the TimescaleDB extension (e.g. Render's managed Postgres) the
dashboard buckets use PostgreSQL's `date_bin`.

---

# Development

Start backend

```bash
uvicorn src.api.main:app --reload
```

Start frontend

```bash
cd frontend
npm run dev
```

---

# Common Issues

## Backend won't start

Verify

- Docker containers are running
- PostgreSQL is accessible
- `.env` is configured correctly

---

## Dashboard shows no data

Ensure

- Dataset has been imported
- Transactions exist in the database
- Backend is connected to PostgreSQL

---

## Login fails

Check

- Analyst account exists
- JWT secret is configured
- Backend is running

---

# Future Improvements

- Live Kafka transaction streaming
- Role-based access control
- Real-time WebSocket alerts
- Email and Slack alert integration
- Analyst assignment workflow
- Advanced fraud investigation dashboard

---

# Contributors

- SN Bose Team

---

## License

This project was developed as part of an internship/academic project. All rights are reserved by the project contributors unless stated otherwise.
