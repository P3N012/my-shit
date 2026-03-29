# InsightPlus Backend

Marketing Analytics Platform - Backend API

Built with **FastAPI**, **PostgreSQL**, **SQLAlchemy**

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- PostgreSQL 13+
- pip
- virtualenv (recommended)

### 2. Installation

```bash
# Clone/navigate to project
cd insightplus-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create PostgreSQL database
createdb insightplus_dev

# Or with specific user:
psql -U postgres
CREATE DATABASE insightplus_dev;
CREATE USER insightplus_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE insightplus_dev TO insightplus_user;
\q
```

### 4. Environment Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

**Required .env variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `ACCESS_TOKEN_SECRET` - JWT secret (generate random string)
- `REFRESH_TOKEN_SECRET` - JWT secret (generate random string)
- `GOOGLE_ADS_*` - Google Ads API credentials
- `META_APP_*` - Meta Ads API credentials

**Generate secure secrets:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

### 5. Initialize Database

```bash
# Create tables
python scripts/init_db.py

# Seed with test data
python scripts/seed_db.py
```

### 6. Run Server

```bash
# Development mode (auto-reload)
python main.py

# Or with uvicorn directly:
uvicorn app.main:app --reload

# Server runs on: http://localhost:8000
```

### 7. Test API

Visit: `http://localhost:8000/docs` for interactive API documentation (Swagger UI)

---

## 📁 Project Structure

```
insightplus-backend/
├── app/
│   ├── core/                  # Core configuration
│   │   ├── config.py          # Settings management
│   │   ├── database.py        # Database connection
│   │   └── security.py        # JWT & password hashing
│   ├── models/                # SQLAlchemy models
│   │   ├── user.py
│   │   ├── platform_connection.py
│   │   ├── campaign.py
│   │   ├── metric.py
│   │   ├── sync_log.py
│   │   ├── analytics_raw.py
│   │   ├── insight.py
│   │   └── report_preference.py
│   ├── schemas/               # Pydantic schemas (request/response)
│   ├── routes/                # API endpoints
│   ├── services/              # Business logic
│   └── main.py                # FastAPI app
├── scripts/
│   ├── init_db.py             # Create database tables
│   └── seed_db.py             # Seed test data
├── tests/                     # Unit tests
├── main.py                    # Server entry point
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

---

## 🗄️ Database Models

### Core Models:
- **User** - Authentication & accounts
- **RefreshToken** - JWT token management
- **PlatformConnection** - OAuth tokens for Google/Meta Ads
- **Campaign** - Marketing campaigns
- **Metric** - Daily performance data
- **SyncLog** - Sync operation tracking
- **AnalyticsRaw** - Granular audience data
- **Insight** - AI-generated alerts
- **ReportPreference** - Email report settings

### Relationships:
```
User
├── RefreshTokens (1:N)
├── PlatformConnections (1:N)
│   ├── Campaigns (1:N)
│   │   └── Metrics (1:N)
│   └── SyncLogs (1:N)
├── Insights (1:N)
└── ReportPreferences (1:N)
```

---

## 🔐 Authentication

### JWT Token System:
- **Access Token**: 30 minutes (for API requests)
- **Refresh Token**: 30 days (for getting new access tokens)

### Endpoints (to be implemented):
- `POST /api/v1/auth/register` - Create account
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user

---

## 🔗 OAuth Integration

### Supported Platforms:
- Google Ads
- Meta Ads (Facebook/Instagram)

### OAuth Flow (to be implemented):
1. User clicks "Connect Platform"
2. Redirect to platform OAuth page
3. User authorizes
4. Platform redirects back with code
5. Exchange code for tokens
6. Store tokens in `platform_connections` table

---

## 🧪 Testing

### Test Credentials (after seeding):
- **Email**: `test@insightplus.com`
- **Password**: `password123`

### Test Admin:
- **Email**: `admin@insightplus.com`
- **Password**: `admin123`

### Run Tests (when implemented):
```bash
pytest
```

---

## 📊 API Endpoints (Planned)

### Authentication
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

### OAuth
- `POST /api/v1/oauth/google-ads/connect`
- `GET /api/v1/oauth/google-ads/callback`
- `POST /api/v1/oauth/meta-ads/connect`
- `GET /api/v1/oauth/meta-ads/callback`

### Connections
- `GET /api/v1/connections`
- `GET /api/v1/connections/{id}`
- `POST /api/v1/connections/{id}/sync`
- `DELETE /api/v1/connections/{id}`

### Campaigns
- `GET /api/v1/campaigns`
- `GET /api/v1/campaigns/{id}`

### Dashboard
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/dashboard/trends`

### Insights
- `GET /api/v1/insights`
- `POST /api/v1/insights/{id}/dismiss`

---

## 🛠️ Development

### Run in Development Mode:
```bash
# Auto-reload on code changes
python main.py

# Or
uvicorn app.main:app --reload
```

### Database Migrations (Alembic):
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Style:
- Follow PEP 8
- Use type hints
- Add docstrings to functions
- Keep functions small and focused

---

## 🚨 Common Issues

### Issue 1: "ModuleNotFoundError"
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### Issue 2: "database does not exist"
```bash
# Create database
createdb insightplus_dev
```

### Issue 3: "password authentication failed"
```bash
# Check DATABASE_URL in .env
# Make sure username, password match PostgreSQL
```

### Issue 4: "Cannot connect to database"
```bash
# Check if PostgreSQL is running
pg_isready

# Start PostgreSQL (depends on OS)
# Mac: brew services start postgresql
# Linux: sudo service postgresql start
```

---

## 📝 Environment Variables

See `.env.example` for all required variables.

**Security Note:**
- Never commit `.env` to git
- Use strong random secrets in production
- Rotate secrets regularly

---

## 🚀 Deployment (Later)

### Production Checklist:
- [ ] Set `ENVIRONMENT=production` in .env
- [ ] Use secure random secrets
- [ ] Enable HTTPS
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Set up monitoring
- [ ] Use production-grade server (gunicorn)

---

## 📚 Documentation

- FastAPI Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

---

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Write tests
4. Submit pull request

---

## 📄 License

Proprietary - All Rights Reserved

---

## 🆘 Need Help?

- Check this README
- Review code comments
- Check FastAPI docs: https://fastapi.tiangolo.com/
- Check SQLAlchemy docs: https://docs.sqlalchemy.org/

---

**Built with ❤️ for InsightPlus**