from pathlib import Path
from flask import Blueprint, render_template, send_from_directory, current_app, abort, Response, jsonify
from app.services.branch_service import BranchService

static_bp = Blueprint("static_pages", __name__)

@static_bp.route("/about", methods=["GET"])
def about_view():
    branches = BranchService.get_popular_branches(limit=30)
    return render_template("about.html", branches=branches)

@static_bp.route("/rules", methods=["GET"])
def rules_view():
    branches = BranchService.get_popular_branches(limit=30)
    return render_template("rules.html", branches=branches)

@static_bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename: str):
    # Prevent directory traversal
    safe_name = Path(filename).name
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    disk_target = upload_dir / safe_name

    # 1. Quick disk cache lookup
    if disk_target.exists() and disk_target.is_file():
        response = send_from_directory(str(upload_dir), safe_name, mimetype="image/webp")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # 2. Database DispatchMedia lookup (guarantees images persist on serverless cold reboots)
    stem = Path(safe_name).stem
    from app.models import DispatchMedia
    from app.extensions import db
    media = db.session.execute(
        db.select(DispatchMedia).where(
            db.or_(DispatchMedia.filename == safe_name, DispatchMedia.id == stem)
        )
    ).scalar_one_or_none()

    if media:
        # Re-populate local container disk cache if directory is writable
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            with open(disk_target, "wb") as f:
                f.write(media.data)
        except Exception:
            pass

        response = Response(media.data, mimetype=media.mimetype)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["Content-Length"] = str(media.size_bytes)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    abort(404)

@static_bp.route("/manifest.json", methods=["GET"])
def pwa_manifest():
    manifest_data = {
        "name": "Kotonoki (言の木)",
        "short_name": "Kotonoki",
        "description": "A quiet public journal and chronological micro-publishing system.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#eef3f8",
        "theme_color": "#2b579a",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)

@static_bp.route("/sw.js", methods=["GET"])
def service_worker():
    sw_code = """
const CACHE_NAME = 'kotonoki-v4';
const STATIC_ASSETS = [
  '/',
  '/static/css/tokens.css',
  '/static/css/explorer.css',
  '/static/css/sticky.css',
  '/static/js/htmx.min.js',
  '/static/icons/icon-192.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // 1. Only intercept GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // 2. Only intercept same-origin requests (ignore chrome-extension, CDNs, etc.)
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  // 3. Network first for HTML navigation
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  // 4. Cache first for static assets, network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    return;
  }
});
"""
    return Response(sw_code, mimetype="application/javascript")
