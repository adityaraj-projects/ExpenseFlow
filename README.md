# ExpenseFlow — Production-Grade Personal Expense & Finance SaaS

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://www.mysql.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![QA Tests Passed](https://img.shields.io/badge/QA%20Tests-155%2F155%20Passed-brightgreen.svg)](#-automated-qa-test-suite)
[![PWA Ready](https://img.shields.io/badge/PWA-Installable-blueviolet.svg)](#9--progressive-web-app-pwa--offline-shell)
[![Web Push](https://img.shields.io/badge/Web%20Push-VAPID%20Ready-success.svg)](#10--reminders-in-app-notifications--web-push)

**ExpenseFlow** is a modern, production-grade personal finance and expense management web application engineered with clean RESTful architecture, strict multi-tenant data isolation, relational integrity, progressive web app (PWA) capabilities, recurring transaction automation, and a premium fintech-style user experience.

Developed as an **MCA Academic & Portfolio Capstone Project**, ExpenseFlow demonstrates real-world software engineering practices: database normalization, foreign key constraints, connection pooling, cryptographically secure JWT authentication, responsive mobile design, interactive Chart.js visualizations, Service Worker caching, and standards-compliant Web Push notifications.

---

## 🌟 Key Features

### 1. 🔐 Cryptographic Authentication & Multi-Tenant Security
- **Bcrypt Password Hashing**: Passwords are never stored in plaintext; salted and hashed with work-factor cost.
- **JWT Authorization**: Cryptographically signed bearer token verification with expiration enforcement on all protected routes.
- **Strict Data Isolation**: Every transaction, category, budget, savings goal, reminder, and recurring template query is strictly scoped to the authenticated user ID (`user_id == current_user.id`).
- **Session Protection**: Seamless redirection for unauthenticated access, gracefully handled expiration, and zero password exposure in API payloads.

### 2. 📊 Real-Time Financial Dashboard
- **KPI Summary Cards**: Total Balance, Month Income, Month Expenses, and Remaining Budget with tabular numerical precision.
- **Upcoming Reminders & Recurring Widgets**: Immediate visibility into upcoming bills and scheduled automated transactions on the home dashboard.
- **Cash Flow Trend Chart**: 6-month historical rolling bar chart powered by Chart.js.
- **Category Distribution Doughnut**: Interactive breakdown of spending percentages by category.
- **Recent Activity Feed**: Tabular live feed of recorded transactions.
- **Active Budgets & Savings Progress**: Real-time spending progress bars and milestone completion trackers.

### 3. 💳 Advanced Transaction Management
- **Full CRUD Operations**: Create, view, edit, and delete transactions.
- **Live Instant Search**: Debounced search across transaction descriptions and category names.
- **Multi-Field Filters**: Filter by transaction type (Income/Expense), Category, Date range, and Amount range.
- **Server-Side Pagination & Sorting**: Sort by date or amount with configurable page sizes.
- **Dynamic Filter Aggregates**: Real-time calculated totals (Filtered Income, Filtered Expenses, Net Balance) for any active query.

### 4. 🎯 Monthly Category Budgets & Smart Threshold Alerts
- Set category-specific monthly spending limits with duplicate-prevention constraints.
- Real-time SQL aggregation computing actual expenditures vs. budget targets.
- Visual warning badges and progress bar indicators (`safe` <80%, `warning` 80–100%, `exceeded` >100%).
- **Automated Threshold Notifications**: In-app and push alerts generated idempotently when spending reaches 80% and 100%+ of allocated budget.

### 5. 🏷️ Category Management & Safeguards
- Pre-seeded default categories upon registration (Food, Travel, Shopping, Bills, Rent, Groceries, Salary, Freelance, Investments, etc.).
- Custom category creation with personalized color palettes and icons.
- **Foreign Key Protection**: `ON DELETE RESTRICT` constraint prevents accidental deletion of categories linked to active transactions.

### 6. 🏆 Savings Goals Tracker
- Milestone creation with target amounts and completion deadlines.
- Interactive **Deposit & Withdraw Funds** modal with automatic milestone completion transitions.
- Over-withdrawal guards preventing withdrawals greater than current savings balances.
- Automated milestone and deadline alerts.

### 7. 📈 Deep Reports & Analytics
- Multi-timeframe selectors: **This Week**, **This Month**, **Last Month**, **This Year**, and **Custom Date Ranges**.
- Intelligent date aggregation displaying clean, readable X-axis labels without repetitive or crowded ticks.
- Rich hover tooltips revealing exact calendar dates (`exact_date`).
- Financial health KPIs: Net Savings, Savings Rate (%), and Daily Average Spend.

### 8. ⏰ Bill Reminders & Calendar-Safe Recurrence
- Dedicated reminders management with calendar-safe recurrence (`once`, `daily`, `weekly`, `monthly`, `yearly`).
- Calendar day clamping prevents date skips on shorter months (e.g., January 31 advances cleanly to February 28/29).
- Actionable controls: Mark as Completed (auto-advancing recurring bills), Snooze (+N days), Edit, and Delete.
- Status filters: Pending, Snoozed, Completed, or All.

### 9. 🔄 Recurring Transactions Engine
- Automated template manager for recurring expenses and income (subscriptions, rent, salaries, gym memberships).
- **Idempotent Occurrence Generation**: Compound checks guarantee that a recurring transaction is never duplicated on the same occurrence date.
- Status management: Pause, Resume, and Delete.
- Manual on-demand execution: "Check Due Now" button processes due items immediately.

### 10. 🔔 In-App Notifications & Web Push Alerts
- **Notification Center**: Header bell icon with real-time unread badge counter and slide-out notification flyout.
- **Mark Single & Mark All Read**: Instant client and database state synchronization.
- **Web Push Notifications**: Standards-compliant Web Push (RFC 8291/8292) using VAPID keys, delivered directly to desktop and mobile notifications via Service Worker.
- **User Notification Preferences**: Granular settings toggles for Web Push, Budget Alerts, Bill Reminders, Savings Goal Milestones, and Recurring Transactions.

### 11. 📱 Progressive Web App (PWA) & Offline Shell
- **Standalone Installability**: Standard Web App Manifest (`manifest.webmanifest`) enabling "Install App" or "Add to Home Screen" on Android, iOS, Windows, and macOS.
- **Custom PWA Branding**: Complete suite of high-resolution rounded icons (192px, 512px, 512px maskable) and badge icons.
- **Service Worker (`sw.js`)**: Static app shell caching (HTML, CSS, JS, icons) for ultra-fast startup and instant navigation.
- **Strict Financial Privacy Isolation**: All authenticated API requests (`/api/*`) strictly bypass offline caches directly to the network. No sensitive financial data is ever stored unencrypted in browser cache storages.
- **Offline Banner & Fallback**: Elegant non-intrusive offline indicator and standalone `offline.html` fallback view when network connectivity is lost.

### 12. 🎨 UI/UX & Design System
- **Dark Mode / Light Mode**: System and user-toggleable theme with persistent storage in `localStorage`.
- **Responsive Layout**: Desktop sidebar (250px), tablet-optimized grids, and mobile bottom navigation bar.
- **Currency Support**: Native support for **INR (₹)** formatting with Indian numbering system alongside multi-currency selection.
- **Shimmer Skeletons**: Synchronized CSS pulse animations during asynchronous data fetching.

---

## 🛠️ Technology Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript (ES6+) | Clean modular architecture without heavy frontend framework dependencies |
| **Visualizations** | Chart.js 4.4+ | Canvas-based responsive financial trend charts and distribution doughnuts |
| **Backend** | Python 3.10+ / FastAPI | High-performance asynchronous REST API framework |
| **ASGI Server** | Uvicorn / Gunicorn | High-concurrency production ASGI server |
| **ORM** | SQLAlchemy 2.0+ | Declarative object-relational mapping with connection pooling |
| **Database** | MySQL 8.0+ / MariaDB | ACID-compliant relational database with foreign keys, cascade rules, and indexes |
| **Database Driver** | PyMySQL + Cryptography | Pure-Python MySQL 8+ driver (no C++ build tools required on Windows/Linux) |
| **Security** | Bcrypt + Python-JOSE | Salted password hashing and signed JWT token handling |
| **Validation** | Pydantic v2 + Email-Validator | Strict schema typing, data serialization, and request sanitization |

---

## 📁 Project Directory Structure

```
expense-flow/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point, CORS, static mounts, lifespan
│   │   ├── scheduler.py                # Standalone background scheduler CLI runner
│   │   ├── core/
│   │   │   ├── config.py               # Settings, VAPID credentials, scheduler secret
│   │   │   ├── security.py             # Bcrypt hashing & JWT operations
│   │   │   └── dependencies.py         # DB session & get_current_user injection
│   │   ├── database/
│   │   │   ├── connection.py           # Engine, connection pool & schema synchronizer
│   │   │   └── base.py                 # Declarative Base
│   │   ├── models/
│   │   │   ├── user.py                 # User model with cascade relationships
│   │   │   ├── category.py             # Category model & unique constraints
│   │   │   ├── transaction.py          # Transactions (FK to users, categories, recurring)
│   │   │   ├── budget.py               # Monthly budget allocations
│   │   │   ├── savings_goal.py         # Savings targets & deposit tracking
│   │   │   ├── reminder.py             # Bill reminders with calendar recurrence
│   │   │   ├── recurring_transaction.py# Recurring transaction templates
│   │   │   ├── notification.py         # In-app notifications with idempotency keys
│   │   │   ├── push_subscription.py    # Web Push browser subscriptions
│   │   │   └── user_preference.py      # Notification & alert user toggles
│   │   ├── schemas/                    # Pydantic v2 validation models
│   │   ├── routers/                    # REST API endpoint modules
│   │   │   ├── auth.py                 # /api/auth
│   │   │   ├── categories.py           # /api/categories
│   │   │   ├── transactions.py         # /api/transactions
│   │   │   ├── budgets.py              # /api/budgets
│   │   │   ├── savings.py              # /api/goals
│   │   │   ├── dashboard.py            # /api/dashboard
│   │   │   ├── reports.py              # /api/reports
│   │   │   ├── reminders.py            # /api/reminders
│   │   │   ├── recurring.py            # /api/recurring-transactions
│   │   │   ├── notifications.py        # /api/notifications
│   │   │   ├── push.py                 # /api/push (VAPID, Web Push subscribe)
│   │   │   ├── preferences.py          # /api/preferences
│   │   │   └── scheduler.py            # /api/scheduler/process (Protected webhook)
│   │   └── services/                   # Business logic & aggregation services
│   │       ├── dashboard_service.py    # Summary metrics & sync on load
│   │       ├── report_service.py       # Multi-timeframe chart aggregation
│   │       ├── reminder_service.py     # Calendar-safe recurrence & snooze
│   │       ├── recurring_service.py    # Occurrence generation & idempotency
│   │       ├── push_service.py         # Web Push delivery & VAPID management
│   │       ├── notification_service.py # Idempotent notifications & preferences
│   │       └── scheduler_service.py    # Unified background event processor
│   ├── database/
│   │   ├── schema.sql                  # MySQL DDL initialization script
│   │   └── seed.py                     # Realistic demo data populator (development only)
│   ├── test_qa_suite.py                # 155-assertion automated QA test suite
│   ├── requirements.txt                # Python package dependencies
│   ├── .env.example                    # Template environment variables
│   └── .env                            # Local environment variables (Git-ignored)
├── frontend/
│   ├── index.html                      # Marketing landing page (PWA-enabled)
│   ├── offline.html                    # Standalone offline fallback view
│   ├── manifest.webmanifest            # W3C Web App Manifest
│   ├── sw.js                           # Service Worker (Cache shell + Network-only API)
│   ├── icons/                          # PWA icons (192px, 512px, 512px maskable, 72px badge)
│   ├── pages/
│   │   ├── login.html                  # Sign in UI with demo quick-fill
│   │   ├── register.html               # Registration UI with live strength meter
│   │   ├── dashboard.html              # Central SaaS dashboard
│   │   ├── transactions.html           # Filterable transaction table & modals
│   │   ├── budgets.html                # Monthly budgets & progress bars
│   │   ├── categories.html             # Custom category manager
│   │   ├── goals.html                  # Savings goals & fund adjustments
│   │   ├── reminders.html              # Bill reminders & recurrence manager
│   │   ├── recurring.html              # Recurring transactions template manager
│   │   ├── reports.html                # Deep analytics & comparisons
│   │   ├── profile.html                # Profile info & password updates
│   │   └── settings.html               # Notification preferences & data backup
│   ├── css/
│   │   ├── style.css                   # Core design tokens (Light & Dark variables)
│   │   ├── auth.css                    # Auth cards & password strength bars
│   │   ├── dashboard.css               # Shell layout, notification flyout, PWA banners
│   │   └── responsive.css              # Breakpoints (390px - 1920px) & mobile navigation
│   └── js/
│       ├── api.js                      # Configurable fetch client with JWT interceptors
│       ├── auth.js                     # Auth guards, app shell navigation, PWA installer
│       ├── utils.js                    # Currency formatters, dates, debounce, SVGs
│       ├── toast.js                    # Toast notification manager
│       ├── notifications.js            # Notification center flyout & push manager
│       ├── reminders.js                # Reminders controller
│       ├── recurring.js                # Recurring templates controller
│       ├── dashboard.js                # Dashboard controller & Chart.js instances
│       ├── transactions.js             # Transactions controller & skeleton loader
│       ├── budgets.js                  # Budgets controller & progress calculations
│       ├── categories.js               # Categories controller
│       ├── goals.js                    # Savings goals controller
│       └── reports.js                  # Analytics charts controller
├── .gitignore                          # Git ignore rules (secrets, venv, temporary logs)
└── README.md                           # Documentation
```

---

## 🗄️ Database Schema & Relational Design

```
+---------------------------------------------------------------------------------------------------+
|                                               USERS                                               |
| PK  id                  INT AUTO_INCREMENT                                                        |
|     full_name           VARCHAR(100) NOT NULL                                                     |
|     email               VARCHAR(191) NOT NULL UNIQUE [INDEX]                                      |
|     password_hash       VARCHAR(255) NOT NULL                                                     |
|     currency            VARCHAR(10)  NOT NULL DEFAULT 'INR'                                       |
|     created_at          DATETIME NOT NULL                                                         |
|     updated_at          DATETIME NOT NULL                                                         |
+---+------------------+-------------------+---------------------+------------------+---------------+
    | 1                | 1                 | 1                   | 1                | 1
    | 1:N (CASCADE)    | 1:N (CASCADE)     | 1:N (CASCADE)       | 1:N (CASCADE)    | 1:N (CASCADE)
    v                  v                   v                     v                  v
+------------+   +--------------+   +-------------+   +-----------------+   +--------------------+
| CATEGORIES |   | TRANSACTIONS |   |   BUDGETS   |   |  SAVINGS_GOALS  |   |     REMINDERS      |
| PK id      |   | PK id        |   | PK id       |   | PK id           |   | PK id              |
| FK user_id |   | FK user_id   |   | FK user_id  |   | FK user_id      |   | FK user_id         |
|    name    |   | FK cat_id    |   | FK cat_id   |   |    name         |   | FK cat_id          |
|    type    |   | FK rec_tx_id |   |    amount   |   |    target_amt   |   |    title           |
|    icon    |   |    type      |   |    month    |   |    current_amt  |   |    amount          |
|    color   |   |    amount    |   |    year     |   |    target_date  |   |    reminder_date   |
+-----+------+   |    trans_date|   +------+------+   +-----------------+   |    recurrence      |
      | 1        +------+-------+          ^                                |    status          |
      |                 ^                  |                                +--------------------+
      +-----------------+ (1:N RESTRICT)   |
      |                 |                  |
      +-----------------+------------------+ (1:N CASCADE)
      |
      +---------------------------------------------------------------------+
      | 1 (CASCADE)                        | 1 (CASCADE)                    | 1 (CASCADE)
      v                                    v                                v
+--------------------------+   +-----------------------+   +-------------------------+
|  RECURRING_TRANSACTIONS  |   |     NOTIFICATIONS     |   |   PUSH_SUBSCRIPTIONS    |
| PK id                    |   | PK id                 |   | PK id                   |
| FK user_id               |   | FK user_id            |   | FK user_id              |
| FK cat_id                |   |    title              |   |    endpoint UNIQUE      |
|    frequency             |   |    message            |   |    p256dh               |
|    amount                |   |    type               |   |    auth                 |
|    next_occurrence_date  |   |    is_read            |   +-------------------------+
|    status                |   |    idempotency_key UNQ|
+--------------------------+   +-----------------------+
```

- **Monetary Precision**: All monetary amounts use `DECIMAL(12, 2)` to eliminate binary floating-point rounding inaccuracies.
- **Relational Integrity**: `transactions.category_id` specifies `ON DELETE RESTRICT`, preventing accidental removal of categories that contain transactions.
- **Account Deletion Cascade**: When a user account is deleted, child records in `categories`, `transactions`, `budgets`, and `savings_goals` cascade cleanly without orphan records.
- **Unique Constraints**: Budgets enforce a compound unique constraint on `(user_id, category_id, month, year)` preventing duplicate monthly allocations.

---

## 🚀 Local Installation & Setup

### Prerequisites
- Python 3.10 or higher
- MySQL Server 8.0+ or MariaDB 10.5+
- Modern Web Browser (Chrome, Firefox, Safari, Edge)

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/expense-flow.git
cd expense-flow
```

### Step 2: Configure MySQL Database
Start your MySQL server and initialize the database:
```sql
CREATE DATABASE IF NOT EXISTS expense_flow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
*(Optionally, import `backend/database/schema.sql` via MySQL CLI or MySQL Workbench).*

### Step 3: Set Up Python Virtual Environment
```bash
cd backend
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the template configuration to `.env`:
```bash
cp .env.example .env
```
Edit `backend/.env` with your database credentials:
```env
PROJECT_NAME="ExpenseFlow"
ENVIRONMENT="development"
DEBUG=True

# MySQL connection string (adjust username, password, host, and port)
DATABASE_URL="mysql+pymysql://root:your_password@localhost:3306/expense_flow?charset=utf8mb4"

# JWT Secret (minimum 32 characters)
JWT_SECRET="replace-with-a-secure-random-secret-key-minimum-32-characters"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Allowed CORS Origins
CORS_ORIGINS="http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000"
```

### Step 5: Seed Sample Data (Optional Development Only)
```bash
python database/seed.py
```
This initializes a demo profile for quick testing:
- **Email**: `demo@expenseflow.com`
- **Password**: `Password123!`
- Includes 16 categories, 55+ realistic transactions across 90 days, monthly budgets, and active savings goals.

### Step 6: Start Backend Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Step 7: Access the Application
Open your browser at:
- **Web Application**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger Interactive API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Interactive Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Automated QA Test Suite

ExpenseFlow includes a comprehensive automated test suite in [`backend/test_qa_suite.py`](backend/test_qa_suite.py) testing all modules against the live database:

```bash
cd backend
python test_qa_suite.py
```

### Test Coverage Highlights (155/155 Assertions Passed):
1. **Database Schema & Constraints**: Verifies existence of all 10 MySQL tables and foreign keys (including `recurring_transactions`).
2. **Authentication & Password Security**: Tests registration, Bcrypt hash validation, `/api/auth/me`, invalid passwords, and token expiration.
3. **Categories CRUD**: Validates custom category creation, editing, and blocks deletion when transactions are linked (`ON DELETE RESTRICT`).
4. **Transactions CRUD**: Tests income and expense recording, live search, multi-field filtering, pagination, and real-time dashboard total updates.
5. **Strict User Data Isolation**: Creates two distinct users and verifies that User A cannot read, edit, or delete any record belonging to User B (returning 404 or 403).
6. **Budget Calculations**: Tests monthly spending computation, duplicate rejection, and automatic state transitions (`safe`, `warning`, `exceeded`).
7. **Savings Goals Lifecycle**: Verifies initial amounts, deposits, withdrawals, over-withdrawal guards, and auto-completion.
8. **Reports Timeframes & Readability**: Verifies `this_week`, `this_month`, `last_month`, `this_year`, exact date tooltips, and non-repeating X-axis labels.
9. **API Error Handling**: Validates HTTP 400, 401, 404, and 422 error codes with sanitized messages.
10. **Relational Integrity**: Confirms 0 orphan records across `transactions`, `budgets`, `savings_goals`, `reminders`, `recurring_transactions`, `notifications`, `push_subscriptions`, and `user_preferences`.
11. **Reminders System & Calendar-Safe Recurrence**: Verifies reminder creation, snooze (+N days), completion, auto-advancement of recurring bills, and user isolation.
12. **Recurring Transactions & Idempotency**: Verifies template creation, on-demand generation (`/process-now`), pause/resume, and guarantees 0 duplicate occurrences.
13. **In-App Notifications & Threshold Alerts**: Verifies unread counter, read-single, read-all, budget threshold notifications (80% and 100%+), and user isolation.
14. **Web Push Subscriptions & Preferences**: Verifies VAPID public key retrieval, browser push subscription upserts, idempotent re-subscription, and preference toggles.
15. **PWA Static Shell & Background Scheduler**: Verifies `manifest.webmanifest`, `sw.js` cache logic, `offline.html`, binary icon assets, and standalone CLI scheduler execution.

---

## ⏰ Background Scheduler & Automation

ExpenseFlow includes a unified background event processor that monitors:
1. **Due Reminders**: Dispatches in-app alerts and Web Push notifications for pending/snoozed reminders whose date is on or before today.
2. **Due Recurring Transactions**: Automatically records transaction entries for active recurring templates whose `next_occurrence_date <= today` and advances them to the next cycle with strict idempotency.
3. **Budget Threshold Warnings**: Automatically generates warnings when monthly category spending crosses 80% or exceeds 100% of the allocated budget.
4. **Savings Goal Milestones**: Alerts users when savings milestones are achieved or target dates approach.

### Running the Scheduler

#### Option 1: Standalone One-Shot Cron (Recommended for Cron / Cloud Schedulers)
Add a cron job (or Windows Task Scheduler task) to run every hour:
```bash
# Linux / macOS cron
0 * * * * cd /path/to/expense-flow/backend && ./venv/bin/python -m app.scheduler >> /var/log/expenseflow_scheduler.log 2>&1

# Windows Task Scheduler
python -m app.scheduler
```

#### Option 2: Continuous Background Daemon
Run as a continuous persistent background process:
```bash
python -m app.scheduler --loop --interval 3600
```

#### Option 3: Protected HTTP Webhook
Invoke the secure scheduler webhook from external cron providers (e.g. AWS EventBridge, Google Cloud Scheduler, GitHub Actions):
```bash
curl -X POST https://your-domain.com/api/scheduler/process \
  -H "X-Scheduler-Key: your_scheduler_secret_key"
```

---

## 🏗️ Production Deployment Architecture

```
                      +-----------------------------+
                      |   Client Web Browser        |
                      |   (Desktop, Tablet, Mobile) |
                      +--------------+--------------+
                                     |
                                HTTPS (TLS)
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
+-------------------------------+             +-------------------------------+
|  Option A: Monolithic Serving |             |  Option B: Decoupled Frontend |
|  FastAPI serves static files  |             |  Vercel / Netlify / Cloudflare|
|  directly from /frontend      |             |  Static Edge CDN              |
+---------------+---------------+             +--------------+----------------+
                |                                            |
                |                                    REST API Requests
                |                                            |
                +--------------------+-----------------------+
                                     |
                                     v
                      +------------------------------+
                      |  FastAPI Backend (ASGI)      |
                      |  Uvicorn + Gunicorn Workers  |
                      |  Docker / AWS / Render / VPS |
                      +--------------+---------------+
                                     |
                             SQLAlchemy Connection
                             Pool (Pre-ping enabled)
                                     |
                                     v
                      +------------------------------+
                      |  MySQL 8.0+ Database Server  |
                      |  Managed Cloud SQL / RDS     |
                      +------------------------------+
```

### Production Environment Configuration
In production, create a secure `.env` file:
```env
PROJECT_NAME="ExpenseFlow"
ENVIRONMENT="production"
DEBUG=False

# Managed database connection string
DATABASE_URL="mysql+pymysql://<db_user>:<db_password>@<db_host>:3306/<db_name>?charset=utf8mb4"

# Cryptographically random secret (generate using: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET="<your-generated-random-32-byte-secret>"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Restrict CORS to your verified domain(s) only
CORS_ORIGINS="https://expenseflow.com,https://app.expenseflow.com"
```

### Recommended Production Execution Commands

#### Linux / Container Production (Gunicorn with Uvicorn Workers):
```bash
# Gunicorn is included in requirements.txt (installed automatically on Linux/macOS/containers)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### Standalone Uvicorn Multi-Worker Production:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend API URL Configuration
- **Monolithic (FastAPI serving static files)**: No configuration needed. The API client automatically uses relative `/api`.
- **Decoupled (Frontend on CDN/Vercel, Backend on separate domain)**:
  Provide the production API base URL by setting `window.EXPENSEFLOW_API_URL` in an inline script or configuring your build:
  ```html
  <script>
    window.EXPENSEFLOW_API_URL = 'https://api.expenseflow.com/api';
  </script>
  ```

---

## 🔒 Security Summary

1. **Password Security**: Passwords hashed with `bcrypt` (cost factor 12). Plaintext passwords are never logged or stored.
2. **No Data Leakage**: Sensitive attributes (`password_hash`) are explicitly omitted from all response schemas.
3. **Cross-Tenant Isolation**: Enforced at the database query level on every endpoint using `current_user.id`.
4. **SQL Injection Prevention**: All queries utilize SQLAlchemy ORM with bound parameters; no raw SQL concatenation.
5. **CORS Hardening**: Configurable allowed origins preventing unauthorized cross-origin browser requests.
6. **Secrets Isolation**: All database passwords and cryptographic keys reside in `.env`, excluded by `.gitignore`.
7. **Production Guard on Seeder**: `seed.py` is protected from running in production environments without an explicit `--force-production` override.

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
Developed for educational, academic, and portfolio demonstration purposes.
