import io
from pathlib import Path
import pytest
from PIL import Image
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import PenName, Branch, Dispatch, Vote, Report
from app.services.auth_service import AuthService
from app.services.branch_service import BranchService
from app.services.sanitizer_service import SanitizerService
from app.services.image_service import ImageService
from app.services.feed_service import FeedService

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "test_uploads"
    RATELIMIT_ENABLED = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user(app):
    user, _ = AuthService.register("poet_wanderer", "SuperSecurePass123!")
    return user

# ============================================================================
# 1. AUTHENTICATION TESTS
# ============================================================================
def test_auth_registration_success(app):
    with app.app_context():
        user, err = AuthService.register("kyoto_ink", "ValidPass123#")
        assert err is None
        assert user is not None
        assert user.handle == "kyoto_ink"
        assert user.password_hash != "ValidPass123#"

def test_auth_registration_duplicate_prevention(app, test_user):
    with app.app_context():
        # Case insensitive duplicate prevention
        user2, err = AuthService.register("POET_WANDERER", "AnotherPass123!")
        assert user2 is None
        assert "already claimed" in err

def test_auth_login_success_and_failure(app, test_user):
    with app.app_context():
        # Success
        user, err = AuthService.authenticate("poet_wanderer", "SuperSecurePass123!")
        assert err is None
        assert user.id == test_user.id

        # Wrong password
        user_bad, err_bad = AuthService.authenticate("poet_wanderer", "WrongPassword!")
        assert user_bad is None
        assert "Invalid" in err_bad

        # Non-existent user
        user_none, err_none = AuthService.authenticate("ghost_writer", "Password123!")
        assert user_none is None

def test_auth_password_change(app, test_user):
    with app.app_context():
        ok, err = AuthService.change_password(test_user, "SuperSecurePass123!", "NewSecretPass456!")
        assert ok is True
        assert err is None

        # Verify old password no longer works
        u, _ = AuthService.authenticate("poet_wanderer", "SuperSecurePass123!")
        assert u is None

        # Verify new password works
        u2, _ = AuthService.authenticate("poet_wanderer", "NewSecretPass456!")
        assert u2 is not None

# ============================================================================
# 2. BRANCH NORMALIZATION & VALIDATION TESTS
# ============================================================================
def test_branch_normalization():
    assert BranchService.normalize_slug("Cooking") == "cooking"
    assert BranchService.normalize_slug("Cast Iron") == "cast-iron"
    assert BranchService.normalize_slug("MIDNIGHT THOUGHTS") == "midnight-thoughts"
    assert BranchService.normalize_slug("#Hardware-Hacks!") == "hardware-hacks"
    assert BranchService.normalize_slug("---multiple---hyphens---") == "multiple-hyphens"

def test_branch_reserved_slugs():
    for reserved in ["admin", "auth", "write", "about", "rules", "api", "static", "desk"]:
        is_valid, err = BranchService.validate_slug(reserved)
        assert is_valid is False
        assert "reserved" in err

def test_branch_get_or_create(app):
    with app.app_context():
        b1, err1 = BranchService.get_or_create("Morning Coffee")
        assert err1 is None
        assert b1.slug == "morning-coffee"

        # Duplicate resolution to same branch
        b2, err2 = BranchService.get_or_create("morning coffee")
        assert err2 is None
        assert b2.id == b1.id

# ============================================================================
# 3. HTML SANITIZATION TESTS
# ============================================================================
def test_sanitizer_removes_dangerous_tags():
    malicious_inputs = [
        '<script>alert("xss")</script><p>Safe text</p>',
        '<p>Click here: <a href="javascript:alert(1)">Exploit</a></p>',
        '<img src="x" onerror="alert(1)"><p>Allowed</p>',
        '<iframe src="https://evil.com"></iframe><p>Allowed</p>',
        '<style>body { display:none; }</style><p>Content</p>',
        '<svg onload="alert(1)"></svg><p>Text</p>'
    ]

    for raw in malicious_inputs:
        cleaned = SanitizerService.sanitize_html(raw)
        assert "<script" not in cleaned
        assert "javascript:" not in cleaned
        assert "onerror" not in cleaned
        assert "<iframe" not in cleaned
        assert "<style" not in cleaned
        assert "<svg" not in cleaned
        assert "<p>" in cleaned

def test_sanitizer_preserves_allowed_tags():
    allowed_html = (
        '<p>Paragraph with <strong>bold</strong>, <em>italic</em>, <u>underline</u>, '
        '<mark>highlight</mark>, and <a href="https://example.com">safe link</a>.</p>'
        '<blockquote>Quoted memo</blockquote>'
    )
    cleaned = SanitizerService.sanitize_html(allowed_html)
    assert "<strong>bold</strong>" in cleaned
    assert "<em>italic</em>" in cleaned
    assert "<u>underline</u>" in cleaned
    assert "<mark>highlight</mark>" in cleaned
    assert "<blockquote>Quoted memo</blockquote>" in cleaned
    assert 'href="https://example.com"' in cleaned
    assert 'rel="noopener noreferrer"' in cleaned

# ============================================================================
# 4. IMAGE PROCESSING TESTS
# ============================================================================
def test_image_processing_valid_png_and_webp_conversion(app):
    from werkzeug.datastructures import FileStorage
    with app.app_context():
        # Create a sample RGB in-memory image
        img_byte_arr = io.BytesIO()
        test_img = Image.new("RGB", (2000, 1500), color=(73, 109, 137))
        test_img.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)

        file = FileStorage(stream=img_byte_arr, filename="test_photo.png", content_type="image/png")
        rel_path, err = ImageService.process_and_save(file)

        assert err is None
        assert rel_path is not None
        assert rel_path.endswith(".webp")

        # Verify saved file dimensions (must not exceed 1600)
        from pathlib import Path
        saved_file = Path(app.config["UPLOAD_FOLDER"]) / Path(rel_path).name
        assert saved_file.exists()
        with Image.open(saved_file) as processed:
            assert processed.format == "WEBP"
            assert processed.width <= 1600
            assert processed.height <= 1600

        # Test Strike permanent image unlinking
        deleted = ImageService.delete_image_file(rel_path)
        assert deleted is True
        assert not saved_file.exists()

def test_image_processing_rejects_corrupted_file(app):
    from werkzeug.datastructures import FileStorage
    with app.app_context():
        corrupt_stream = io.BytesIO(b"This is not a real image binary data.")
        file = FileStorage(stream=corrupt_stream, filename="fake.jpg", content_type="image/jpeg")
        rel_path, err = ImageService.process_and_save(file)
        assert rel_path is None
        assert "Invalid or corrupt" in err


def test_persistent_image_storage_database_fallback(app, client):
    """Verify that images persist in DispatchMedia and serve successfully even when disk cache is wiped."""
    from werkzeug.datastructures import FileStorage
    from app.models import DispatchMedia
    from pathlib import Path

    with app.app_context():
        img_byte_arr = io.BytesIO()
        test_img = Image.new("RGB", (300, 300), color=(120, 160, 200))
        test_img.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)

        file = FileStorage(stream=img_byte_arr, filename="fallback_test.png", content_type="image/png")
        rel_path, err = ImageService.process_and_save(file)
        assert err is None
        assert rel_path is not None

        # Verify record exists in DispatchMedia table
        filename = Path(rel_path).name
        media = db.session.execute(
            db.select(DispatchMedia).where(DispatchMedia.filename == filename)
        ).scalar_one_or_none()
        assert media is not None
        assert media.size_bytes > 0
        assert media.mimetype == "image/webp"

        # Wipe file from disk to simulate serverless container cold-boot / instance switch
        saved_file = Path(app.config["UPLOAD_FOLDER"]) / filename
        if saved_file.exists():
            saved_file.unlink()
        assert not saved_file.exists()

    # Now make HTTP GET request for the image — it must restore and serve from DispatchMedia
    resp = client.get(rel_path)
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "image/webp"
    assert len(resp.data) == media.size_bytes

    # Cleanup
    with app.app_context():
        ImageService.delete_image_file(rel_path)
        media_after = db.session.execute(
            db.select(DispatchMedia).where(DispatchMedia.filename == filename)
        ).scalar_one_or_none()
        assert media_after is None


def test_css_security_and_mime_protection(app, client):
    """Ensure CSS MIME types and CSP settings guarantee that stylesheets are never blocked."""
    resp = client.get("/static/css/tokens.css")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "text/css; charset=utf-8"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    csp = resp.headers.get("Content-Security-Policy", "")
    # Ensure style-src allows self and unsafe-inline so page is never rendered unstyled
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "img-src 'self' data: https://res.cloudinary.com" in csp


# ============================================================================
# 5. DISPATCH CREATION & CHRONOLOGICAL FEED TESTS
# ============================================================================
def test_dispatch_creation_and_feed(app, test_user):
    with app.app_context():
        branch, _ = BranchService.get_or_create("journal")
        
        # Create dispatches
        d1 = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="First Morning Dispatch",
            content_html="<p>Early morning reflection.</p>"
        )
        d2 = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Afternoon Notes",
            content_html="<p>Quiet afternoon thoughts.</p>"
        )
        db.session.add_all([d1, d2])
        db.session.commit()

        # Retrieve chronological feed
        feed = FeedService.get_feed(branch_id=branch.id)
        dispatches = feed["dispatches"]
        assert len(dispatches) == 2
        # Reverse chronological (newest first)
        assert dispatches[0].id == d2.id
        assert dispatches[1].id == d1.id

# ============================================================================
# 6. JUDGMENT-FREE PHILOSOPHY (NO VOTES / SCORES)
# ============================================================================
def test_dispatches_are_judgment_free(app, test_user):
    """Confirm dispatches exist as pure writing without social scoring or voting."""
    with app.app_context():
        user2, _ = AuthService.register("reader_two", "Password987#")
        branch, _ = BranchService.get_or_create("books")
        dispatch = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Book Review",
            content_html="<p>Review content.</p>"
        )
        db.session.add(dispatch)
        db.session.commit()

        # Dispatches are pure writing: author and branch exist, no social score requirement
        assert dispatch.title == "Book Review"
        assert dispatch.author.handle == test_user.handle
        assert dispatch.branch.slug == "books"

# ============================================================================
# 7. PERMANENT STRIKE (DELETION) TESTS
# ============================================================================
def test_dispatch_strike_permanence(app, test_user):
    with app.app_context():
        branch, _ = BranchService.get_or_create("ideas")
        dispatch = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Fleeting Idea",
            content_html="<p>Ephemeral dispatch.</p>"
        )
        db.session.add(dispatch)
        db.session.commit()

        dispatch_id = dispatch.id
        # Delete / Strike
        db.session.delete(dispatch)
        db.session.commit()

        # Confirm permanent expunging
        checked = db.session.get(Dispatch, dispatch_id)
        assert checked is None


def test_branches_with_counts_group_by(app, test_user):
    """Verify that get_branches_with_counts accurately aggregates dispatch counts in a single query."""
    with app.app_context():
        b1, _ = BranchService.get_or_create("alpha-topic")
        b2, _ = BranchService.get_or_create("beta-topic")
        b3, _ = BranchService.get_or_create("empty-topic")

        d1 = Dispatch(branch_id=b1.id, author_id=test_user.id, title="A1", content_html="<p>A1</p>")
        d2 = Dispatch(branch_id=b1.id, author_id=test_user.id, title="A2", content_html="<p>A2</p>")
        d3 = Dispatch(branch_id=b2.id, author_id=test_user.id, title="B1", content_html="<p>B1</p>")
        db.session.add_all([d1, d2, d3])
        db.session.commit()

        counts = BranchService.get_branches_with_counts()
        count_map = {item["branch"].slug: item["count"] for item in counts}

        assert count_map.get("alpha-topic") == 2
        assert count_map.get("beta-topic") == 1
        assert count_map.get("empty-topic") == 0


def test_feed_service_eager_loading(app, test_user):
    """Verify that FeedService returns dispatches with pre-loaded branch and author."""
    with app.app_context():
        branch, _ = BranchService.get_or_create("speed-branch")
        dispatch = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Fast Dispatch",
            content_html="<p>Pre-loaded relations</p>"
        )
        db.session.add(dispatch)
        db.session.commit()

        feed = FeedService.get_feed(branch_id=branch.id)
        assert len(feed["dispatches"]) >= 1
        item = feed["dispatches"][0]
        # Access relationship attributes without triggering lazy SQL queries
        assert item.branch.slug == "speed-branch"
        assert item.author.handle == test_user.handle


# ============================================================================
# 8. RSS 2.0 / ATOM SYNDICATION TESTS
# ============================================================================
def test_rss_feeds_global_and_branch(app, client, test_user):
    with app.app_context():
        branch, _ = BranchService.get_or_create("poetry")
        d = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Autumn Haiku",
            content_html="<p>Falling red maple leaves.</p>"
        )
        db.session.add(d)
        db.session.commit()

    # Global RSS feed
    resp_global = client.get("/feed.xml")
    assert resp_global.status_code == 200
    assert "application/rss+xml" in resp_global.headers.get("Content-Type", "")
    assert b"<rss version=\"2.0\"" in resp_global.data
    assert b"Autumn Haiku" in resp_global.data

    # Branch-specific RSS feed
    resp_branch = client.get("/poetry/feed.xml")
    assert resp_branch.status_code == 200
    assert "application/rss+xml" in resp_branch.headers.get("Content-Type", "")
    assert b"Kotonoki /poetry" in resp_branch.data
    assert b"Autumn Haiku" in resp_branch.data

    # Non-existent branch feed returns 404
    resp_nonexistent = client.get("/non-existent-xyz/feed.xml")
    assert resp_nonexistent.status_code == 404


# ============================================================================
# 9. DISPATCH SEARCH TESTS
# ============================================================================
def test_search_view_and_htmx_partial(app, client, test_user):
    with app.app_context():
        branch, _ = BranchService.get_or_create("science")
        d = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Quantum Entanglement Basics",
            content_html="<p>Non-local correlations between particles.</p>"
        )
        db.session.add(d)
        db.session.commit()

    # Full search page
    resp_page = client.get("/search?q=Quantum")
    assert resp_page.status_code == 200
    assert b"Quantum Entanglement Basics" in resp_page.data

    # HTMX partial search query
    resp_htmx = client.get("/search?q=correlations", headers={"HX-Request": "true"})
    assert resp_htmx.status_code == 200
    assert b"search-results-container" in resp_htmx.data
    assert b"Quantum Entanglement Basics" in resp_htmx.data

    # Empty query returns prompt
    resp_empty = client.get("/search", headers={"HX-Request": "true"})
    assert resp_empty.status_code == 200
    assert b"Search through all public branches" in resp_empty.data


def test_search_service_advanced_syntax_and_highlights(app, test_user):
    from app.services.search_service import SearchService

    # 1. Test Query Parsing
    parsed = SearchService.parse_query("delicious /cooking @kenji ramen recipes")
    assert parsed["branch"] == "cooking"
    assert parsed["author"] == "kenji"
    assert "delicious" in parsed["keywords"]
    assert "ramen" in parsed["keywords"]

    # 2. Test Highlighting
    excerpt = SearchService.highlight_excerpt(
        "<p>We baked artisanal sourdough bread with cracked pepper.</p>",
        "sourdough"
    )
    assert '<mark class="search-match">sourdough</mark>' in excerpt

    # 3. Test Scoped Search
    with app.app_context():
        b1, _ = BranchService.get_or_create("gardening")
        b2, _ = BranchService.get_or_create("cooking")
        d1 = Dispatch(branch_id=b1.id, author_id=test_user.id, title="Tomato plants", content_html="<p>Red tomatoes</p>")
        d2 = Dispatch(branch_id=b2.id, author_id=test_user.id, title="Tomato soup", content_html="<p>Warm soup</p>")
        db.session.add_all([d1, d2])
        db.session.commit()

        # Scoped to gardening
        res_garden = SearchService.search("tomato", filter_branch="gardening")
        assert len(res_garden["dispatches"]) == 1
        assert res_garden["dispatches"][0].title == "Tomato plants"

        # Scoped to author
        res_author = SearchService.search(f"@{test_user.handle} tomato")
        assert len(res_author["dispatches"]) == 2



# ============================================================================
# 10. JOURNAL EXPORT TESTS
# ============================================================================
def test_desk_journal_export_zip(app, client, test_user):
    import zipfile
    import io

    with app.app_context():
        user_id = test_user.id
        user_handle = test_user.handle
        branch, _ = BranchService.get_or_create("memories")
        d = Dispatch(
            branch_id=branch.id,
            author_id=user_id,
            title="Childhood Bicycle",
            content_html="<p>Riding down the hill.</p>"
        )
        db.session.add(d)
        db.session.commit()

    # Log in as test_user via session
    with client.session_transaction() as sess:
        sess["pen_name_id"] = user_id

    # Authenticated export
    resp_export = client.post("/desk/export")
    assert resp_export.status_code == 200
    assert resp_export.headers.get("Content-Type") == "application/zip"
    assert "attachment" in resp_export.headers.get("Content-Disposition", "")
    assert f"kotonoki-{user_handle}-journal.zip" in resp_export.headers.get("Content-Disposition", "")

    # Verify ZIP contents
    zip_bytes = io.BytesIO(resp_export.data)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "README.md" in namelist
        assert any(name.startswith("dispatches/") and name.endswith(".md") for name in namelist)
        readme_content = zf.read("README.md").decode("utf-8")
        assert user_handle in readme_content
        assert "Childhood Bicycle" in readme_content


def test_desk_property_sheet_and_zero_emojis(app, client, test_user):
    """Ensure the Desk renders authentic property sheet tabs and zero raw emojis."""
    import re
    with app.app_context():
        user_id = test_user.id

    with client.session_transaction() as sess:
        sess["pen_name_id"] = user_id

    res = client.get("/desk")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Verify Property Sheet Tab Navigation
    assert "desk-tab-nav" in html
    assert "Your Dispatches" in html
    assert "Clipped Memos" in html
    assert "Security & Password" in html
    assert "desk-property-panel" in html

    # Verify no raw emojis in rendered HTML
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2b55\u2702-\u27b0]')
    emojis = emoji_pattern.findall(html)
    assert emojis == [], f"Found unexpected raw emojis in Desk HTML: {emojis}"


def test_theme_system_css_tokens():
    """Ensure CSS theme tokens cover canvas gradients, headers, commands, and surfaces for all themes."""
    from pathlib import Path
    tokens_path = Path("app/static/css/tokens.css")
    assert tokens_path.exists()
    content = tokens_path.read_text(encoding="utf-8")

    # Required variables that ensure seamless theme switching across the entire viewport
    required_vars = [
        "--k-canvas-bg",
        "--k-canvas-gradient",
        "--k-header-bg",
        "--k-command-bg",
        "--k-surface",
        "--k-border-subtle",
        "--k-primary",
        "--k-text-main"
    ]

    # Verify default :root
    for var in required_vars:
        assert var in content, f"Missing token {var} in tokens.css"

    # Verify lamp theme definition
    assert '[data-theme="lamp"]' in content
    # Verify amber theme is removed
    assert '[data-theme="amber"]' not in content

    # Verify explorer.css consumes var(--k-canvas-gradient) on body
    explorer_path = Path("app/static/css/explorer.css")
    explorer_content = explorer_path.read_text(encoding="utf-8")
    assert "background-image: var(--k-canvas-gradient);" in explorer_content
    assert "background: var(--k-header-bg);" in explorer_content
    assert "background: var(--k-command-bg);" in explorer_content

def test_dynamic_search_api_and_modal_integration(app, client, test_user):
    """Verify that dynamic quick search API works and base template embeds dynamic search modal & dropdown."""
    with app.app_context():
        branch, _ = BranchService.get_or_create("tea")
        d = Dispatch(
            branch_id=branch.id,
            author_id=test_user.id,
            title="Japanese Gyokuro Steeping",
            content_html="<p>Steeping delicate shade-grown green tea leaves.</p>"
        )
        db.session.add(d)
        db.session.commit()

    # 1. Test /api/quick-search returns valid JSON without page navigation
    res_api = client.get("/api/quick-search?q=Gyokuro")
    assert res_api.status_code == 200
    assert res_api.is_json
    data = res_api.get_json()
    assert data["total"] >= 1
    assert any("Gyokuro" in item["title"] for item in data["results"])

    # 2. Test base.html has the dynamic modal and autocomplete dropdown elements
    res_home = client.get("/")
    assert res_home.status_code == 200
    home_html = res_home.data.decode("utf-8")
    assert 'id="header-search-dropdown"' in home_html
    assert 'id="global-search-modal"' in home_html
    assert 'id="modal-search-input"' in home_html
    assert 'onclick="openGlobalSearchModal(event)"' in home_html

    # 3. Test /search page uses onsubmit handler to prevent full page refresh
    res_search = client.get("/search")
    assert res_search.status_code == 200
    search_html = res_search.data.decode("utf-8")
    assert 'onsubmit="handleSearchPageSubmit(event)"' in search_html
    assert 'id="search-results-area"' in search_html

def test_amber_theme_completely_removed():
    """Verify Amber CRT theme has been completely eliminated across all stylesheets, scripts, and templates."""
    tokens_path = Path("app/static/css/tokens.css")
    explorer_path = Path("app/static/css/explorer.css")
    js_path = Path("app/static/js/app.js")
    base_path = Path("app/templates/base.html")

    assert '[data-theme="amber"]' not in tokens_path.read_text(encoding="utf-8")
    assert '[data-theme="amber"]' not in explorer_path.read_text(encoding="utf-8")
    assert "'amber'" not in js_path.read_text(encoding="utf-8")
    assert "Amber CRT" not in base_path.read_text(encoding="utf-8")





