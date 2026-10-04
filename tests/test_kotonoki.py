import io
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
# 6. VOTING MECHANICS TESTS
# ============================================================================
def test_voting_lifecycle(app, test_user):
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

        # Upvote from user2
        v1 = Vote(dispatch_id=dispatch.id, author_id=user2.id, value=1)
        db.session.add(v1)
        dispatch.upvotes_count = 1
        db.session.commit()

        assert dispatch.score == 1
        assert dispatch.upvotes_count == 1

        # Unique constraint prevention on duplicate vote
        with pytest.raises(Exception):
            v_dup = Vote(dispatch_id=dispatch.id, author_id=user2.id, value=1)
            db.session.add(v_dup)
            db.session.commit()
        db.session.rollback()

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
