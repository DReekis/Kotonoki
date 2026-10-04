# Deploying Kotonoki (言の木) to Vercel

Kotonoki is fully prepared for zero-configuration or custom deployment on **Vercel Serverless Functions** with Python.

---

## Architecture Overview

- **Entry Point**: [`api/index.py`](api/index.py) provides the WSGI application callable for Vercel's `@vercel/python` serverless runtime.
- **Routing**: [`vercel.json`](vercel.json) routes all incoming HTTP traffic to `api/index.py`.
- **Dependencies**: [`requirements.txt`](requirements.txt) includes Flask, SQLAlchemy, Argon2, Pillow, and `psycopg2-binary` for managed PostgreSQL databases.
- **Bundle Optimization**: [`.vercelignore`](.vercelignore) prevents local test caches and node modules from inflating the serverless function bundle.
- **Filesystem Compatibility**: The application automatically routes file operations to `/tmp` when running in Vercel's serverless environment.

---

## Method 1: Deploy with GitHub (Recommended)

1. Push your Kotonoki repository to GitHub.
2. Go to [vercel.com](https://vercel.com) and log in.
3. Click **Add New...** → **Project**.
4. Import your GitHub repository.
5. In the **Configure Project** screen:
   - **Framework Preset**: Leave as *Other* (Vercel will detect `vercel.json`).
   - **Root Directory**: `./`
6. Click **Deploy**.

---

## Method 2: Deploy with Vercel CLI

1. Install the Vercel CLI globally (if not installed):
   ```bash
   npm i -g vercel
   ```
2. In the Kotonoki project root directory, run:
   ```bash
   vercel
   ```
3. Follow the CLI prompts to link and deploy your project.
4. For production deployment, run:
   ```bash
   vercel --prod
   ```

---

## Database Configuration

### Option A: Instant Zero-Config Fallback (SQLite in `/tmp`)
If you deploy without configuring any database, Kotonoki automatically uses SQLite located in `/tmp/kotonoki.db` and seeds the authentic sample dispatches on first boot. 

> **Note**: `/tmp` is ephemeral and specific to serverless instance lifecycles.

### Option B: Persistent Production Database (PostgreSQL)
For production persistence, connect any PostgreSQL database (Neon, Supabase, Vercel Postgres, Render, ElephantSQL, etc.):

1. In your Vercel Project Dashboard, navigate to **Settings** → **Environment Variables**.
2. Add:
   - **`DATABASE_URL`**: Your PostgreSQL connection string (e.g., `postgresql://user:pass@ep-silent-wave.neon.tech/kotonoki?sslmode=require`).
   - **`SECRET_KEY`**: A strong random string for cryptographic session signing.
   - **`FLASK_ENV`**: `production`
3. Kotonoki automatically normalizes `postgres://` prefixes to `postgresql://` and creates all tables on cold start.
