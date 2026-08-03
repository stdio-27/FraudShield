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

```bash
python3 -m venv shieldenv
```

Activate

### macOS / Linux

```bash
source shieldenv/bin/activate
```

### Windows

```bash
shieldenv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

# Environment Variables

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fraudshield

REDIS_URL=redis://localhost:6379

SECRET_KEY=your-secret-key

FRONTEND_PRODUCTION_URL=http://localhost:5173

ALERT_THRESHOLD=0.85
```

---

# Start Infrastructure

Run Docker services:

```bash
docker compose up -d
```

This starts

- PostgreSQL
- TimescaleDB
- Redis
- pgAdmin

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

Place the file as

```
data/
    creditcard.csv
```

On first startup, the application automatically imports the dataset into PostgreSQL if the transaction table is empty.

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

Default credentials

Email

```
admin@fraudshield.com
```

Password

```
admin
```

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

1. Load trained XGBoost model
2. Engineer transaction features
3. Predict fraud probability
4. Generate SHAP explanations
5. Store prediction in database
6. Generate alerts for high-risk transactions

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
