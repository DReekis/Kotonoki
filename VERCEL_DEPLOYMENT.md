# Deploying Kotonoki (言の木) to Vercel

Kotonoki is fully prepared for zero-configuration and production deployment on **Vercel Serverless Functions** with Python.

---

## 1. What to Use for Database & Storage

Because Vercel serverless functions have a read-only filesystem (with an ephemeral `/tmp` directory that clears between cold boots), you should use managed cloud services for production:

| Component | Recommended Service | Free Tier Allowance | Why |
| :--- | :--- | :--- | :--- |
| **Database** | **Neon Postgres** *(or Supabase)* | 0.5 GB (Neon) / 500 MB (Supabase) | **Best for Vercel:** Scale-to-zero, connection pooling, 1-click integration in Vercel dashboard. |
| **Storage (Images)** | **Cloudinary** | 25 GB managed storage & bandwidth | **Easiest for Media:** Generous free tier, global CDN delivery, no credit card required, instant Python integration. |

---

## 2. Recommended Database: Neon Postgres

### How to Set Up Neon (Option 1: Directly inside Vercel Dashboard)
1. In your Vercel Project Dashboard, click the **Storage** tab at the top.
2. Click **Create Database** and choose **Neon** (or Postgres).
3. Follow the quick setup. Vercel will automatically inject the `DATABASE_URL` environment variable into your project.
4. Redeploy your project. Kotonoki will automatically detect `DATABASE_URL`, create all tables on cold start, and seed initial dispatches!

### How to Set Up Supabase (Option 2)
1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **Project Settings** → **Database** → **Connection String** → choose **URI** (Session mode or Transaction pooler, port 5432 or 6543).
3. In Vercel Project Settings → **Environment Variables**, add:
   - `DATABASE_URL`: Your Supabase connection string.

---

## 3. Recommended Storage: Cloudinary (for Image Uploads)

### Why Cloudinary?
When users attach images to dispatches, Kotonoki strips EXIF metadata, resizes them, and converts them to clean WebP format. Storing them on Cloudinary ensures images persist permanently across all serverless function instances with global CDN caching.

### How to Set Up Cloudinary:
1. Sign up for a free account at [cloudinary.com](https://cloudinary.com).
2. On your Cloudinary Dashboard, copy your **API Environment variable**:
   ```
   CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
   ```
3. In Vercel Project Settings → **Environment Variables**, add:
   - `CLOUDINARY_URL`: `cloudinary://<api_key>:<api_secret>@<cloud_name>`
4. That's it! Kotonoki will automatically detect `CLOUDINARY_URL` and route all uploaded WebP images directly to Cloudinary.

*(If `CLOUDINARY_URL` is omitted, Kotonoki will fallback to storing images temporarily in `/tmp/uploads` for local/testing environments).*

---

## 4. Environment Variables Checklist in Vercel

Under **Project Settings** → **Environment Variables**, configure the following:

| Variable | Value | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://...` | Persistent database connection (Neon / Supabase). |
| `CLOUDINARY_URL` | `cloudinary://...` | Persistent media storage for attached images. |
| `SECRET_KEY` | `random_long_string_here` | Cryptographic signing for session cookies. |
| `FLASK_ENV` | `production` | Enforces production cookie security. |

---

## 5. Deployment Methods

### Method 1: Deploy with GitHub (Recommended)
1. Push your Kotonoki repository to GitHub.
2. In [vercel.com](https://vercel.com), click **Add New...** → **Project**.
3. Import your GitHub repository.
4. Keep the Framework Preset as **Other** and Root Directory as `./`.
5. Enter the Environment Variables listed above.
6. Click **Deploy**.

### Method 2: Deploy with Vercel CLI
```bash
npm i -g vercel
vercel
```
To deploy to production:
```bash
vercel --prod
```
