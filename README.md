# LADLI Electrical Testing & Calibration Laboratory
### Web Platform, Visitor Management System & Admin Portal

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?style=flat&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-black.svg?style=flat&logo=flask)](https://palletsprojects.com/p/flask/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supported-336791.svg?style=flat&logo=postgresql)](https://www.postgresql.org/)
[![SQLite](https://img.shields.io/badge/SQLite-Zero--Config-003B57.svg?style=flat&logo=sqlite)](https://www.sqlite.org/)
[![Three.js](https://img.shields.io/badge/Three.js-3D--Visuals-000000.svg?style=flat&logo=threedotjs)](https://threejs.org/)
[![Status](https://img.shields.io/badge/Status-Production--Ready-success.svg?style=flat)](#)

A high-performance, self-contained web platform, client enquiry hub, and visitor management system built for **LADLI Electrical Testing and Calibration Laboratory Pvt. Ltd.** (Vadodara, Gujarat, India).

The system integrates a 41-page modern frontend with 3D interactive physics and animations, a dual-database Python (Flask) backend (PostgreSQL + SQLite), an automated visitor tracking system, and an authenticated administrative portal for managing customer enquiries and technical document downloads.

---

## Table of Contents

- [Overview & Architecture](#overview--architecture)
- [Key Features](#key-features)
  - [1. 41-Page Public Website](#1-41-page-public-website)
  - [2. Visitor Management System](#2-visitor-management-system)
  - [3. Admin Management Portal](#3-admin-management-portal)
  - [4. Dual-Database Engine (PostgreSQL + SQLite)](#4-dual-database-engine-postgresql--sqlite)
  - [5. Automated Email Notifications](#5-automated-email-notifications)
- [Project Directory Structure](#project-directory-structure)
- [Getting Started (Local Development)](#getting-started-local-development)
  - [Prerequisites](#prerequisites)
  - [One-Click Launchers](#one-click-launchers)
  - [Manual Setup](#manual-setup)
  - [Initial Admin Login](#initial-admin-login)
- [Environment Variables & Configuration](#environment-variables--configuration)
- [Database Setup & Migration](#database-setup--migration)
  - [Using SQLite (Default)](#using-sqlite-default)
  - [Using PostgreSQL](#using-postgresql)
  - [Migrating from SQLite to PostgreSQL](#migrating-from-sqlite-to-postgresql)
- [Admin CLI Tools](#admin-cli-tools)
- [Deployment Guide](#deployment-guide)
  - [PythonAnywhere](#pythonanywhere)
  - [Production VPS / PaaS (Render, Railway, Docker)](#production-vps--paas-render-railway-docker)
- [Pushing to GitHub Safely](#pushing-to-github-safely)
- [Brand & Contact Reference](#brand--contact-reference)

---

## Overview & Architecture

```mermaid
graph TD
    User([Public Visitor]) -->|Browses Site / Submits Forms| WebFrontend[41-Page Responsive Web Frontend]
    WebFrontend -->|API Requests: /api/contact, /api/quote, /api/visitors| FlaskApp[Flask Backend: app.py]
    
    AdminUser([Laboratory Admin]) -->|Secured /admin Portal| AdminUI[Admin Management Portal]
    AdminUI -->|Authenticated APIs: /api/admin/*| FlaskApp

    FlaskApp -->|Data Access Layer: db.py| DBAdapter{Database Engine}
    DBAdapter -->|Production| PostgresDB[(PostgreSQL)]
    DBAdapter -->|Local Zero-Config| SQLiteDB[(SQLite: data/ladli.db)]

    FlaskApp -->|SMTP TLS| MailServer[Gmail / Corporate SMTP Server]
    MailServer -->|Quote Confirmation & Password Reset| User
    
    MigrateTool[CLI: migrate_sqlite_to_postgres.py] -->|Sync Data| PostgresDB
```

---

## Key Features

### 1. 41-Page Public Website
- **Comprehensive Electrical Testing Coverage**: Dedicated pages for Dissolved Gas Analysis (DGA), Breakdown Voltage (BDV), Karl Fischer Moisture, Dielectric Dissipation Factor (Tan Delta), Specific Resistance / Resistivity, Interfacial Tension (IFT), Acidity, Flash Point, Sludge/Sediment, and more.
- **Interactive 3D Visualizations (Three.js)**: Custom 3D models embedded across key pages (molecular DGA gas clusters, transformer coils, laboratory vials, and radar locator), automatically paused when out of viewport for optimal performance.
- **Micro-Animations & Physics**: Fluid hero heading reveals, smooth number counters, and magnetic button hovers powered by `anime.js` and subtle drifting particle fields with `tsParticles`.
- **100% Self-Hosted & Zero External CDN Dependencies**: All vendor libraries (`three.min.js`, `anime.min.js`, `tsparticles.slim.min.js`) and typography (`Inter` woff2) are hosted locally under `site/assets/`. Operates completely offline or behind strict firewalls.
- **Glassmorphism & Responsive Layout**: Tailored responsive layouts tested across Mobile (375px–390px), Tablet (768px–834px), and Desktop/Laptop (1120px–1440px+).

### 2. Visitor Management System
- **Unique Visitor Tracking**: Automated, privacy-conscious visitor logging using client-generated tokens stored via `localStorage` and synced via `/api/visitors`.
- **Dual Counter Modes (`/admin/visitors`)**:
  - **Auto Mode**: Accurately tracks unique visitors visiting the website.
  - **Manual Baseline Mode**: Allows lab administrators to configure a verified baseline count for display on the public website footer.
- **Real-Time Live Previews**: Admins can preview changes and switch modes instantly from the dashboard.

### 3. Admin Management Portal
- **Dashboard (`/admin`)**: Real-time KPI cards displaying total enquiries, active quotes, documents published, and visitor statistics.
- **Enquiry Management**: Review client contact submissions and quote requests. Filter by status (`New`, `In Review`, `Contacted`, `Closed`) and view attached testing parameters.
- **Document Management (`/admin/documents`)**: Upload technical specifications, NABL documentation, brochures, and test standards (PDFs up to 25MB) directly to the public Downloads library.
- **Enterprise-Grade Security**:
  - Brute-force protection: Automatic IP lockout after 5 consecutive failed login attempts (15-minute lockout).
  - Enforced password change on first login.
  - Email-based password reset workflow with cryptographically signed, expiring tokens (`/admin/forgot-password` and `/admin/reset-password`).
  - Session-based CSRF protection and HTTP-only cookie authentication.

### 4. Dual-Database Engine (PostgreSQL + SQLite)
- **Zero-Config Local SQLite**: Automatically creates and initializes `data/ladli.db` with all required tables, indexes, and an initial admin account on first boot.
- **Production PostgreSQL Support**: Native integration with `psycopg2-binary`, connection pooling (`ThreadedConnectionPool`), dictionary cursors, and schema auto-migration.
- **1-Click SQLite to PostgreSQL Migration**: Includes `migrate_sqlite_to_postgres.py` to seamlessly port existing enquiries, admin users, documents, and visitor logs to cloud databases.

### 5. Automated Email Notifications
- **Customer Quote Acknowledgments**: Instant, branded HTML confirmation emails dispatched to clients upon submitting quote forms.
- **Admin Alert Notifications**: Immediate email alerts sent to the lab team when a new enquiry is lodged.
- **Password Reset Deliveries**: Secure transactional links delivered via SMTP.

---

## Project Directory Structure

```
LADLI_visitor-management_fixed/
│
├── app.py                         # Core Flask application, routing, and APIs
├── db.py                          # Dual-database DAL (PostgreSQL + SQLite)
├── requirements.txt               # Python package dependencies
├── .env.example                   # Template for environment configuration
├── .gitignore                     # Git ignore rules (protects credentials & DB)
├── run.bat                        # One-click Windows launcher
├── run.sh                         # One-click Linux/macOS launcher
├── DEPLOYMENT.md                  # Deployment guide for hosting providers
├── wsgi_pythonanywhere.py         # WSGI entry point for PythonAnywhere
│
├── set_admin_password.py          # CLI tool to securely reset admin credentials
├── migrate_sqlite_to_postgres.py  # Data migration tool (SQLite -> PostgreSQL)
├── apply_mobile_protection.py     # Utility script for layout responsiveness
├── apply_favicon_update.py        # Utility script for asset favicons
│
├── admin/                         # Administrative portal UI
│   ├── dashboard.html             # Enquiries & analytics overview
│   ├── visitors.html              # Visitor management & counter configuration
│   ├── settings.html              # Admin password & profile settings
│   ├── login.html                 # Admin login screen with brute-force defense
│   ├── forgot_password.html       # Password reset request screen
│   ├── reset_password.html        # Password reset confirmation screen
│   └── assets/                    # Admin styles and scripts
│
├── site/                          # 41-page public website
│   ├── index.html                 # Homepage with 3D gas molecule hero
│   ├── about.html                 # About the laboratory & team
│   ├── services.html              # Testing & calibration service catalog
│   ├── laboratory.html            # Lab facilities, instrumentation & quality
│   ├── request-quote.html         # Interactive quote calculator/request form
│   ├── contact.html               # Contact details, map & direct enquiry
│   ├── downloads.html             # Live document & certificate repository
│   ├── test-*.html                # Individual testing service landing pages
│   └── assets/                    # Self-hosted vendor scripts, CSS & fonts
│       ├── vendor/                # three.min.js, anime.min.js, tsparticles
│       ├── fonts/                 # Inter Latin woff2 font files
│       ├── images/                # Laboratory photos, test apparatus & logos
│       ├── site.js                # Public frontend logic & visitor beacon
│       └── styles.css             # Main styling system
│
├── data/                          # Local runtime data (ignored by git)
│   ├── .gitkeep                   # Preserves folder in git
│   └── ladli.db                   # SQLite database (auto-generated)
│
├── uploads/                       # Document storage directory (ignored by git)
│   └── .gitkeep                   # Preserves folder in git
│
└── attachments/                   # Temporary file handling
    └── .gitkeep                   # Preserves folder in git
```

---

## Getting Started (Local Development)

### Prerequisites
- **Python 3.9+** installed on your system.
- Optional: **PostgreSQL 12+** (if not using default SQLite).

### One-Click Launchers

#### Windows
Simply double-click `run.bat` or run:
```cmd
run.bat
```

#### Linux / macOS
Grant execution permissions and run:
```bash
chmod +x run.sh
./run.sh
```

### Manual Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd LADLI_visitor-management_fixed
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize environment configuration:**
   Copy the `.env.example` template:
   ```bash
   # Windows
   copy .env.example .env

   # macOS / Linux
   cp .env.example .env
   ```

5. **Start the application:**
   ```bash
   python app.py
   ```

6. Open your web browser and visit:
   - **Public Site**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
   - **Admin Portal**: [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)

---

### Initial Admin Login

On the very first run with a fresh database, the application will generate a secure one-time password and print it to your terminal:

```
================================================================
 First run: an admin account was created.
   Username: admin
   Password: <a-secure-randomly-generated-password>
 This password was randomly generated and is shown ONLY here, once.
 Save it now. You will be required to change it the moment you log in.
================================================================
```

1. Go to [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin).
2. Log in using `admin` and the printed password.
3. You will be prompted to set your new permanent password immediately.

---

## Environment Variables & Configuration

Configure your `.env` file to customize credentials, database connections, and mail delivery:

| Variable | Default / Example | Purpose |
|---|---|---|
| `ADMIN_USERNAME` | `admin` | Initial admin username if creating fresh database. |
| `ADMIN_PASSWORD` | *(Auto-generated)* | Pre-set admin password before initial boot. |
| `ADMIN_EMAIL` | `ladlielec@gmail.com` | Notification recipient for incoming customer enquiries. |
| `DATABASE_URL` | *(None / SQLite)* | PostgreSQL connection URL (`postgresql://user:pass@host:5432/dbname`). |
| `PGHOST` | `localhost` | PostgreSQL host (used if `DATABASE_URL` is omitted). |
| `PGPORT` | `5432` | PostgreSQL port. |
| `PGDATABASE` | `ladli_db` | PostgreSQL database name. |
| `PGUSER` | `postgres` | PostgreSQL username. |
| `PGPASSWORD` | `your-password` | PostgreSQL password. |
| `PGSSLMODE` | `prefer` | SSL mode for Postgres connection (`prefer`, `require`, `disable`). |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP host for sending quote confirmations and reset links. |
| `SMTP_PORT` | `587` | SMTP port (typically 587 for TLS, 465 for SSL). |
| `SMTP_USERNAME` | `your-email@gmail.com` | SMTP username or email address. |
| `SMTP_PASSWORD` | `your-app-password` | SMTP password (use a Google App Password for Gmail). |
| `SMTP_USE_TLS` | `true` | Enable TLS encryption for mail transport. |
| `MAIL_FROM_EMAIL`| `your-email@gmail.com` | Display address on outgoing emails. |
| `MAIL_FROM_NAME` | `LADLI Electrical Testing` | Display sender name. |
| `MAIL_REPLY_TO`  | `your-email@gmail.com` | Reply-to address for client correspondence. |

> **Note on Gmail:** When using Gmail for SMTP, generate an **App Password** (Google Account > Security > 2-Step Verification > App Passwords) rather than your standard account password.

---

## Database Setup & Migration

### Using SQLite (Default)
No setup required. The application automatically creates `data/ladli.db` with all required tables on first startup.

### Using PostgreSQL
To connect to a managed PostgreSQL instance (Render, Supabase, Neon, AWS RDS, Railway, or local PostgreSQL):

1. Add your connection string to `.env`:
   ```env
   DATABASE_URL=postgresql://postgres:secretpassword@localhost:5432/ladli_db
   ```
2. Start the application (`python app.py`). The database schema and initial tables will be verified and created automatically.

### Migrating from SQLite to PostgreSQL
If you have existing data in `data/ladli.db` and wish to migrate to PostgreSQL:

```bash
python migrate_sqlite_to_postgres.py
```
This utility automatically transfers:
- Admin user accounts and password hashes
- Password reset tokens
- Contact form enquiries
- Quote requests
- Uploaded document records
- Unique visitor logs
- System settings and visitor counter configuration

---

## Admin CLI Tools

### Reset Admin Password
If you ever lose access to your admin account, you can reset the password directly from the command line without writing plaintext credentials into files:

```bash
python set_admin_password.py admin "NewSecurePassword123"
```
Or omit the password argument to enter it securely via hidden prompt:
```bash
python set_admin_password.py admin
```

---

## Deployment Guide

### PythonAnywhere
A complete, dedicated deployment guide is provided in [DEPLOYMENT.md](DEPLOYMENT.md).
- Ready-to-use WSGI configuration is provided in [wsgi_pythonanywhere.py](wsgi_pythonanywhere.py).
- Static assets can be mapped directly for high throughput (`/assets/` -> `site/assets/`).

### Production VPS / PaaS (Render, Railway, Docker)
When deploying to production environments:
1. **Production WSGI Server**: Use `gunicorn` (Linux) or `waitress` (Windows):
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```
2. **Reverse Proxy & HTTPS**: Run behind **Nginx** or **Caddy** with automated SSL (Let's Encrypt).
3. **Database**: Provide the `DATABASE_URL` environment variable pointing to your managed PostgreSQL database.
4. **Persistent Storage**: Ensure the `uploads/` directory is mounted to persistent storage or an S3-compatible volume so published PDFs remain available across deployments.

---

## Pushing to GitHub Safely

This repository includes a pre-configured [`.gitignore`](.gitignore) that prevents confidential files, passwords, local databases, and temporary caches from being uploaded.

### Recommended Steps to Initialize and Push:

1. **Verify your local git status:**
   ```bash
   git status
   ```
   *Confirm that `.env` and `data/ladli.db` are **not** listed under untracked files.*

2. **Stage all tracked project files:**
   ```bash
   git add .
   ```

3. **Commit your changes:**
   ```bash
   git commit -m "feat: complete LADLI web platform, visitor management & admin portal"
   ```

4. **Add your GitHub remote repository:**
   ```bash
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   ```

5. **Push to GitHub:**
   ```bash
   git push -u origin main
   ```

> [!IMPORTANT]
> Never commit your real `.env` file or SQLite database containing production enquiries. The provided `.gitignore` automatically excludes `.env`, `data/*.db`, and `data/secret.key`. Always share configurations using `.env.example`.

---

## Brand & Contact Reference

| Detail | Information |
|---|---|
| **Organization** | LADLI Electrical Testing and Calibration Laboratory Pvt. Ltd. |
| **Address** | A/39, First Floor, Shrenik Park, Opp. Akota Stadium, Productivity Road, Akota, Vadodara – 390020, Gujarat, India |
| **Contact Phone** | +91 84908 38981 |
| **Official Email** | ladlielec@gmail.com |
| **Brand Palette** | Royal Blue (`#1F6FE5`) · Sky Blue (`#67C5F8`) · Bright Pink (`#E95AA5`) · Golden Orange (`#F9A825`) |

---

## License & Intellectual Property

Copyright &copy; 2026 LADLI Electrical Testing and Calibration Laboratory Pvt. Ltd. All rights reserved.
