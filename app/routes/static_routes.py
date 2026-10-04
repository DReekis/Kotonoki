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
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_dir, safe_name, mimetype="image/webp")

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
const CACHE_NAME = 'kotonoki-v3';
const STATIC_ASSETS = [
  '/',
  '/static/css/tokens.css',
  '/static/css/explorer.css',
  '/static/css/sticky.css',
  '/static/js/htmx.min.js',
  '/static/js/editor.bundle.js',
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
  // Network first for HTML, cache first for static assets
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
"""
    return Response(sw_code, mimetype="application/javascript")
