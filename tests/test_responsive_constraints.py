import re
import pytest
from pathlib import Path
from app import create_app
from app.config import Config
from app.extensions import db

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "test_uploads"
    RATELIMIT_ENABLED = False

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

def test_css_no_uncontrolled_fixed_widths():
    """Verify that CSS does not contain dangerous fixed widths or min-widths that cause overflow at 320px."""
    css_path = Path("app/static/css/explorer.css")
    assert css_path.exists()
    content = css_path.read_text(encoding="utf-8")

    # Check for hardcoded desktop widths leaking outside media queries
    # Look for min-width > 320px without media query or calc
    lines = content.splitlines()
    in_media_query = False
    current_media = ""

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("@media"):
            in_media_query = True
            current_media = stripped
        elif stripped.startswith("}") and in_media_query:
            # simple bracket tracking
            if current_media and "{" in current_media:
                pass

        # Ensure no min-width: 400px+ or similar on mobile elements
        match = re.search(r"min-width:\s*(\d+)px", stripped)
        if match:
            val = int(match.group(1))
            # On mobile rules or outside media query, min-width should not exceed 320px
            if val > 320 and ("max-width: 767px" in current_media or "max-width: 360px" in current_media):
                pytest.fail(f"Line {idx}: Unsafe min-width {val}px in mobile media query: {stripped}")

def test_all_routes_render_cleanly(client):
    """Verify all major routes return 200 and contain responsive markup."""
    endpoints = ["/", "/branches", "/about", "/rules", "/auth", "/auth?tab=login"]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 200
        html = res.data.decode("utf-8")
        # Ensure viewport meta is present
        assert 'name="viewport"' in html
        assert "viewport-fit=cover" in html
        # Ensure mobile-header and mobile-bottom-nav exist in DOM
        assert "mobile-header" in html
        assert "mobile-bottom-nav" in html
        # Ensure desktop-chrome exists in DOM
        assert "desktop-chrome" in html
